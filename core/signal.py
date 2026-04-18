from datetime import datetime, timedelta
from collections import defaultdict

from core.indicators.base import Signal


STRENGTH_ORDER = {"weak": 1, "medium": 2, "strong": 3}


class SignalEngine:
    def __init__(self, config, logger, indicator_registry, notifier, storage):
        self.config = config
        self.logger = logger
        self.indicator_registry = indicator_registry
        self.notifier = notifier
        self.storage = storage

        signal_cfg = config.get("signal", {})
        self.cooldown_minutes = signal_cfg.get("cooldown_minutes", 15)
        self.max_notifications_per_hour = signal_cfg.get("max_notifications_per_hour", 10)
        self.min_strength = signal_cfg.get("min_strength", "medium")

        self._last_signal_time: dict[str, datetime] = {}
        self._hourly_count: dict[str, int] = defaultdict(int)
        self._hourly_reset: dict[str, datetime] = {}

    async def evaluate(self, key: str, symbol: str, interval: str, price: float):
        df = self.indicator_registry.results.get(key)
        if df is None:
            return

        kline_df = None
        if hasattr(self, '_market_ref') and self._market_ref:
            kline_df = self._market_ref.get_kline_buffer(key)

        if kline_df is None or kline_df.empty:
            return

        all_signals = self.indicator_registry.get_all_signals(key, kline_df)
        if not all_signals:
            return

        filtered = self._filter_signals(all_signals, symbol)
        if not filtered:
            return

        aggregated = self._aggregate_signals(filtered, symbol, price)

        for signal_data in aggregated:
            await self._emit_signal(signal_data, symbol, interval, price)

    def _filter_signals(self, signals: list[Signal], symbol: str) -> list[Signal]:
        min_level = STRENGTH_ORDER.get(self.min_strength, 2)
        filtered = []
        for s in signals:
            if STRENGTH_ORDER.get(s.strength, 0) < min_level:
                continue
            signal_key = f"{symbol}_{s.indicator_name}_{s.signal_type}"
            now = datetime.now()
            last_time = self._last_signal_time.get(signal_key)
            if last_time and (now - last_time) < timedelta(minutes=self.cooldown_minutes):
                continue
            filtered.append(s)
        return filtered

    def _aggregate_signals(self, signals: list[Signal], symbol: str, price: float) -> list[dict]:
        buy_signals = [s for s in signals if s.signal_type == "buy"]
        sell_signals = [s for s in signals if s.signal_type == "sell"]

        results = []

        if len(buy_signals) >= 2:
            strength = self._calc_combined_strength(buy_signals)
            results.append({
                "type": "buy",
                "strength": strength,
                "indicators": [f"{s.indicator_name}: {s.description}" for s in buy_signals],
                "count": len(buy_signals),
                "symbol": symbol,
                "price": price,
            })

        if len(sell_signals) >= 2:
            strength = self._calc_combined_strength(sell_signals)
            results.append({
                "type": "sell",
                "strength": strength,
                "indicators": [f"{s.indicator_name}: {s.description}" for s in sell_signals],
                "count": len(sell_signals),
                "symbol": symbol,
                "price": price,
            })

        return results

    def _calc_combined_strength(self, signals: list[Signal]) -> str:
        if not signals:
            return "weak"
        if len(signals) >= 3:
            return "strong"
        if len(signals) >= 2:
            has_strong = any(s.strength == "strong" for s in signals)
            return "strong" if has_strong else "medium"
        return signals[0].strength

    async def _emit_signal(self, signal_data: dict, symbol: str, interval: str, price: float):
        now = datetime.now()
        hour_key = f"{symbol}_{now.strftime('%Y%m%d%H')}"
        reset_time = self._hourly_reset.get(hour_key)
        if reset_time and (now - reset_time) > timedelta(hours=1):
            self._hourly_count[hour_key] = 0
            self._hourly_reset[hour_key] = now
        elif not reset_time:
            self._hourly_reset[hour_key] = now

        if self._hourly_count.get(hour_key, 0) >= self.max_notifications_per_hour:
            self.logger.warning(f"{symbol} 本小时通知次数已达上限")
            return

        signal_key = f"{symbol}_{signal_data['type']}"
        self._last_signal_time[signal_key] = now
        self._hourly_count[hour_key] = self._hourly_count.get(hour_key, 0) + 1

        strength_label = {"weak": "弱", "medium": "中", "strong": "强"}
        strength_text = strength_label.get(signal_data["strength"], signal_data["strength"])

        if self.storage:
            await self.storage.save_signal(
                symbol=symbol,
                signal_type=signal_data["type"],
                indicator_name="+".join(signal_data["indicators"][:3]),
                indicator_value=str(signal_data.get("count", 1)),
                price=price,
                strength=signal_data["strength"],
            )

        if self.notifier:
            await self.notifier.send_signal(
                symbol=symbol,
                signal_type=signal_data["type"],
                strength=strength_text,
                indicators=signal_data["indicators"],
                price=price,
                interval=interval,
            )

        self.logger.info(
            f"信号触发: {symbol} {signal_data['type']} "
            f"强度={strength_text} "
            f"指标数={signal_data['count']} "
            f"价格={price}"
        )

    async def check_price_alerts(self, symbol: str, price: float):
        for symbol_cfg in self.config.get("symbols", []):
            if symbol_cfg["name"] != symbol:
                continue
            alerts = symbol_cfg.get("price_alerts", [])
            for alert_price in alerts:
                if abs(price - alert_price) / alert_price < 0.001:
                    direction = "突破" if price >= alert_price else "跌破"
                    if self.notifier:
                        await self.notifier.send_price_alert(
                            symbol=symbol,
                            price=price,
                            target=alert_price,
                            direction=direction,
                        )
                    if self.storage:
                        await self.storage.save_price_alert(symbol, price, direction)
                    self.logger.info(f"价格提醒: {symbol} {direction} {alert_price}, 当前={price}")

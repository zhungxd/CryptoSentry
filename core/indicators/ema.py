import pandas as pd
from ta.trend import EMAIndicator as TaEMA

from core.indicators.base import BaseIndicator, Signal


class EMAIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.periods = config.get("periods", [7, 25, 99])

    @property
    def name(self) -> str:
        return "EMA"

    @property
    def description(self) -> str:
        return f"指数移动平均线 (周期:{'/'.join(map(str, self.periods))})"

    def calculate(self, df: pd.DataFrame) -> dict:
        result = {}
        for period in self.periods:
            ema_ind = TaEMA(close=df["close"], window=period)
            ema = ema_ind.ema_indicator()
            def safe(val):
                return round(val, 4) if pd.notna(val) else None
            result[f"ema_{period}"] = safe(ema.iloc[-1])
            result[f"ema_{period}_prev"] = safe(ema.iloc[-2]) if len(ema) > 1 else None
        return result

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        if len(self.periods) < 2:
            return signals

        short_period = self.periods[0]
        long_period = self.periods[1]

        short_val = result.get(f"ema_{short_period}")
        long_val = result.get(f"ema_{long_period}")
        short_prev = result.get(f"ema_{short_period}_prev")
        long_prev = result.get(f"ema_{long_period}_prev")

        if any(v is None for v in [short_val, long_val, short_prev, long_prev]):
            return signals

        if short_prev <= long_prev and short_val > long_val:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="buy",
                strength="strong",
                description=f"EMA金叉: EMA{short_period}({short_val})上穿EMA{long_period}({long_val})",
                value={"short_period": short_period, "long_period": long_period,
                       "short_val": short_val, "long_val": long_val, "cross": "golden"},
            ))
        elif short_prev >= long_prev and short_val < long_val:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="sell",
                strength="strong",
                description=f"EMA死叉: EMA{short_period}({short_val})下穿EMA{long_period}({long_val})",
                value={"short_period": short_period, "long_period": long_period,
                       "short_val": short_val, "long_val": long_val, "cross": "death"},
            ))

        return signals

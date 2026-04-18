import pandas as pd
from ta.volume import OnBalanceVolumeIndicator as TaOBV

from core.indicators.base import BaseIndicator, Signal


class OBVIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.divergence_lookback = config.get("divergence_lookback", 20)

    @property
    def name(self) -> str:
        return "OBV"

    @property
    def description(self) -> str:
        return "能量潮指标（量价背离检测）"

    def calculate(self, df: pd.DataFrame) -> dict:
        obv_ind = TaOBV(close=df["close"], volume=df["volume"])
        obv = obv_ind.on_balance_volume()

        current = obv.iloc[-1]
        return {
            "obv": round(current, 2) if pd.notna(current) else None,
            "series": obv,
        }

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        obv_series = result.get("series")
        if obv_series is None or len(obv_series) < self.divergence_lookback:
            return signals

        lookback = min(self.divergence_lookback, len(df), len(obv_series))
        recent_close = df["close"].iloc[-lookback:]
        recent_obv = obv_series.iloc[-lookback:]

        close_higher = recent_close.iloc[-1] > recent_close.iloc[0]
        obv_lower = recent_obv.iloc[-1] < recent_obv.iloc[0]

        close_lower = recent_close.iloc[-1] < recent_close.iloc[0]
        obv_higher = recent_obv.iloc[-1] > recent_obv.iloc[0]

        if close_higher and obv_lower:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="sell",
                strength="medium",
                description="量价顶背离: 价格上涨但OBV下降，上涨动力不足",
                value={"divergence": "bearish"},
            ))
        elif close_lower and obv_higher:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="buy",
                strength="medium",
                description="量价底背离: 价格下跌但OBV上升，下跌动力衰竭",
                value={"divergence": "bullish"},
            ))

        return signals

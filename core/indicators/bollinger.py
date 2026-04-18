import pandas as pd
from ta.volatility import BollingerBands as TaBB

from core.indicators.base import BaseIndicator, Signal


class BollingerIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.period = config.get("period", 20)
        self.std = config.get("std", 2.0)

    @property
    def name(self) -> str:
        return "Bollinger"

    @property
    def description(self) -> str:
        return f"布林带 (周期:{self.period}, 标准差:{self.std})"

    def calculate(self, df: pd.DataFrame) -> dict:
        bb = TaBB(close=df["close"], window=self.period, window_dev=self.std)
        upper = bb.bollinger_hband()
        middle = bb.bollinger_mavg()
        lower = bb.bollinger_lband()

        def safe(val):
            return round(val, 4) if pd.notna(val) else None

        return {
            "upper": safe(upper.iloc[-1]),
            "middle": safe(middle.iloc[-1]),
            "lower": safe(lower.iloc[-1]),
            "close": round(df["close"].iloc[-1], 4),
        }

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        upper = result.get("upper")
        lower = result.get("lower")
        close = result.get("close")

        if upper is None or lower is None or close is None:
            return signals

        if close <= lower:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="buy",
                strength="strong" if close < lower else "medium",
                description=f"价格触及布林带下轨: 价格={close}, 下轨={lower}",
                value={"close": close, "lower": lower, "upper": upper},
            ))
        elif close >= upper:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="sell",
                strength="strong" if close > upper else "medium",
                description=f"价格触及布林带上轨: 价格={close}, 上轨={upper}",
                value={"close": close, "lower": lower, "upper": upper},
            ))

        return signals

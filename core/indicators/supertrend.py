import pandas as pd
import numpy as np
from ta.volatility import AverageTrueRange as TaATR

from core.indicators.base import BaseIndicator, Signal


class SuperTrendIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.period = config.get("period", 10)
        self.multiplier = config.get("multiplier", 3.0)

    @property
    def name(self) -> str:
        return "SuperTrend"

    @property
    def description(self) -> str:
        return f"SuperTrend趋势指标 (周期:{self.period}, 乘数:{self.multiplier})"

    def calculate(self, df: pd.DataFrame) -> dict:
        atr_ind = TaATR(high=df["high"], low=df["low"], close=df["close"], window=self.period)
        atr = atr_ind.average_true_range()

        hl2 = (df["high"] + df["low"]) / 2
        upper_band = hl2 + self.multiplier * atr
        lower_band = hl2 - self.multiplier * atr

        supertrend = pd.Series(np.nan, index=df.index)
        direction = pd.Series(1, index=df.index, dtype=int)

        for i in range(self.period, len(df)):
            if df["close"].iloc[i] > upper_band.iloc[i - 1]:
                direction.iloc[i] = -1
            elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
                direction.iloc[i] = 1
            else:
                direction.iloc[i] = direction.iloc[i - 1]

            if direction.iloc[i] == -1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]

        def safe(val):
            return round(val, 4) if pd.notna(val) else None

        return {
            "supertrend": safe(supertrend.iloc[-1]),
            "direction": int(direction.iloc[-1]),
            "direction_prev": int(direction.iloc[-2]) if len(direction) > 1 else None,
        }

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        direction = result.get("direction")
        direction_prev = result.get("direction_prev")
        supertrend = result.get("supertrend")

        if direction is None:
            return signals

        if direction_prev is not None and direction_prev != direction:
            close = df["close"].iloc[-1]
            if direction < 0:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="buy",
                    strength="strong",
                    description=f"SuperTrend翻多: 趋势线={supertrend}, 价格={close}",
                    value={"supertrend": supertrend, "direction": "up"},
                ))
            else:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="sell",
                    strength="strong",
                    description=f"SuperTrend翻空: 趋势线={supertrend}, 价格={close}",
                    value={"supertrend": supertrend, "direction": "down"},
                ))

        return signals

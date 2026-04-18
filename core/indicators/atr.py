import pandas as pd
import numpy as np
from ta.volatility import AverageTrueRange as TaATR

from core.indicators.base import BaseIndicator, Signal


class ATRIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.period = config.get("period", 14)

    @property
    def name(self) -> str:
        return "ATR"

    @property
    def description(self) -> str:
        return f"真实波幅 (周期:{self.period})"

    def calculate(self, df: pd.DataFrame) -> dict:
        atr_ind = TaATR(high=df["high"], low=df["low"], close=df["close"], window=self.period)
        atr = atr_ind.average_true_range()

        def safe(val):
            return round(val, 4) if pd.notna(val) else None

        return {
            "atr": safe(atr.iloc[-1]),
            "atr_prev": safe(atr.iloc[-2]) if len(atr) > 1 else None,
        }

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        atr = result.get("atr")
        atr_prev = result.get("atr_prev")
        if atr is None or atr_prev is None:
            return signals

        close = df["close"].iloc[-1]
        atr_pct = (atr / close) * 100

        if atr_pct > 5.0:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="sell",
                strength="weak",
                description=f"波动率异常高: ATR={atr} ({atr_pct:.1f}%)",
                value={"atr": atr, "atr_pct": round(atr_pct, 2)},
            ))
        elif atr_pct < 1.0:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="buy",
                strength="weak",
                description=f"波动率极低，可能酝酿突破: ATR={atr} ({atr_pct:.1f}%)",
                value={"atr": atr, "atr_pct": round(atr_pct, 2)},
            ))

        return signals

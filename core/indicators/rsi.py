import pandas as pd
from ta.momentum import RSIIndicator as TaRSI

from core.indicators.base import BaseIndicator, Signal


class RSIIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.period = config.get("period", 14)
        self.overbought = config.get("overbought", 70)
        self.oversold = config.get("oversold", 30)

    @property
    def name(self) -> str:
        return "RSI"

    @property
    def description(self) -> str:
        return f"相对强弱指数 (周期:{self.period})"

    def calculate(self, df: pd.DataFrame) -> dict:
        rsi_ind = TaRSI(close=df["close"], window=self.period)
        rsi = rsi_ind.rsi()
        current = rsi.iloc[-1] if rsi is not None and not rsi.empty else None
        prev = rsi.iloc[-2] if rsi is not None and len(rsi) > 1 else None
        return {
            "rsi": round(current, 2) if pd.notna(current) else None,
            "rsi_prev": round(prev, 2) if pd.notna(prev) else None,
            "series": rsi,
        }

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        rsi = result.get("rsi")
        rsi_prev = result.get("rsi_prev")
        if rsi is None:
            return signals

        if rsi < self.oversold:
            strength = "strong" if rsi < 20 else "medium"
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="buy",
                strength=strength,
                description=f"RSI({self.period})={rsi}，进入超卖区域",
                value={"rsi": rsi, "zone": "oversold"},
            ))
        elif rsi > self.overbought:
            strength = "strong" if rsi > 80 else "medium"
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="sell",
                strength=strength,
                description=f"RSI({self.period})={rsi}，进入超买区域",
                value={"rsi": rsi, "zone": "overbought"},
            ))

        if rsi_prev is not None:
            if rsi_prev >= self.oversold and rsi < self.oversold:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="buy",
                    strength="medium",
                    description=f"RSI({self.period})跌破超卖线，从{rsi_prev}降至{rsi}",
                    value={"rsi": rsi, "rsi_prev": rsi_prev},
                ))
            elif rsi_prev <= self.overbought and rsi > self.overbought:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="sell",
                    strength="medium",
                    description=f"RSI({self.period})突破超买线，从{rsi_prev}升至{rsi}",
                    value={"rsi": rsi, "rsi_prev": rsi_prev},
                ))

        return signals

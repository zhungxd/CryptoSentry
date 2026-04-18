import pandas as pd
from ta.trend import MACD as TaMACD

from core.indicators.base import BaseIndicator, Signal


class MACDIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.fast = config.get("fast", 12)
        self.slow = config.get("slow", 26)
        self.signal_period = config.get("signal", 9)

    @property
    def name(self) -> str:
        return "MACD"

    @property
    def description(self) -> str:
        return f"移动平均收敛散度 ({self.fast}/{self.slow}/{self.signal_period})"

    def calculate(self, df: pd.DataFrame) -> dict:
        macd_ind = TaMACD(close=df["close"],
                          window_slow=self.slow,
                          window_fast=self.fast,
                          window_sign=self.signal_period)
        macd_line = macd_ind.macd()
        signal_line = macd_ind.macd_signal()
        histogram = macd_ind.macd_diff()

        def safe(val):
            return round(val, 4) if pd.notna(val) else None

        return {
            "macd": safe(macd_line.iloc[-1]),
            "signal": safe(signal_line.iloc[-1]),
            "histogram": safe(histogram.iloc[-1]),
            "macd_prev": safe(macd_line.iloc[-2]) if len(macd_line) > 1 else None,
            "signal_prev": safe(signal_line.iloc[-2]) if len(signal_line) > 1 else None,
            "histogram_prev": safe(histogram.iloc[-2]) if len(histogram) > 1 else None,
        }

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        macd_val = result.get("macd")
        signal_val = result.get("signal")
        macd_prev = result.get("macd_prev")
        signal_prev = result.get("signal_prev")
        histogram = result.get("histogram")
        histogram_prev = result.get("histogram_prev")

        if macd_val is None or signal_val is None:
            return signals

        if macd_prev is not None and signal_prev is not None:
            if macd_prev <= signal_prev and macd_val > signal_val:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="buy",
                    strength="strong",
                    description=f"MACD金叉: DIF={macd_val}, DEA={signal_val}",
                    value={"macd": macd_val, "signal": signal_val, "cross": "golden"},
                ))
            elif macd_prev >= signal_prev and macd_val < signal_val:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="sell",
                    strength="strong",
                    description=f"MACD死叉: DIF={macd_val}, DEA={signal_val}",
                    value={"macd": macd_val, "signal": signal_val, "cross": "death"},
                ))

        if histogram is not None and histogram_prev is not None:
            if histogram > 0 and histogram_prev <= 0:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="buy",
                    strength="medium",
                    description=f"MACD柱线转正: {histogram}",
                    value={"histogram": histogram},
                ))
            elif histogram < 0 and histogram_prev >= 0:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="sell",
                    strength="medium",
                    description=f"MACD柱线转负: {histogram}",
                    value={"histogram": histogram},
                ))

        return signals

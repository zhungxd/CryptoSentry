import pandas as pd
from ta.momentum import StochasticOscillator as TaStoch

from core.indicators.base import BaseIndicator, Signal


class KDJIndicator(BaseIndicator):
    def __init__(self, config: dict):
        self.k_period = config.get("k_period", 9)
        self.d_period = config.get("d_period", 3)
        self.j_period = config.get("j_period", 3)
        self.overbought = config.get("overbought", 80)
        self.oversold = config.get("oversold", 20)

    @property
    def name(self) -> str:
        return "KDJ"

    @property
    def description(self) -> str:
        return f"KDJ随机指标 (K:{self.k_period}, D:{self.d_period}, J:{self.j_period})"

    def calculate(self, df: pd.DataFrame) -> dict:
        stoch = TaStoch(high=df["high"], low=df["low"], close=df["close"],
                        window=self.k_period, smooth_window=self.d_period)
        k = stoch.stoch()
        d = stoch.stoch_signal()

        def safe(val):
            return round(val, 2) if pd.notna(val) else None

        k_val = safe(k.iloc[-1])
        d_val = safe(d.iloc[-1])
        j_val = round(3 * k.iloc[-1] - 2 * d.iloc[-1], 2) if pd.notna(k.iloc[-1]) and pd.notna(d.iloc[-1]) else None

        return {
            "k": k_val,
            "d": d_val,
            "j": j_val if pd.notna(j_val) else None,
            "k_prev": safe(k.iloc[-2]) if len(k) > 1 else None,
            "d_prev": safe(d.iloc[-2]) if len(d) > 1 else None,
        }

    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        signals = []
        k = result.get("k")
        d = result.get("d")
        j = result.get("j")
        k_prev = result.get("k_prev")
        d_prev = result.get("d_prev")

        if k is None or d is None:
            return signals

        if k_prev is not None and d_prev is not None:
            if k_prev <= d_prev and k > d and k < self.oversold:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="buy",
                    strength="strong",
                    description=f"KDJ低位金叉: K={k}, D={d}, J={j}",
                    value={"k": k, "d": d, "j": j, "cross": "golden", "zone": "oversold"},
                ))
            elif k_prev >= d_prev and k < d and k > self.overbought:
                signals.append(Signal(
                    indicator_name=self.name,
                    signal_type="sell",
                    strength="strong",
                    description=f"KDJ高位死叉: K={k}, D={d}, J={j}",
                    value={"k": k, "d": d, "j": j, "cross": "death", "zone": "overbought"},
                ))

        if k < self.oversold:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="buy",
                strength="medium",
                description=f"K值进入超卖区域: K={k}",
                value={"k": k, "zone": "oversold"},
            ))
        elif k > self.overbought:
            signals.append(Signal(
                indicator_name=self.name,
                signal_type="sell",
                strength="medium",
                description=f"K值进入超买区域: K={k}",
                value={"k": k, "zone": "overbought"},
            ))

        return signals

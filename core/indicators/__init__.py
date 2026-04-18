from core.indicators.base import BaseIndicator
from core.indicators.rsi import RSIIndicator
from core.indicators.macd import MACDIndicator
from core.indicators.bollinger import BollingerIndicator
from core.indicators.ema import EMAIndicator
from core.indicators.kdj import KDJIndicator
from core.indicators.atr import ATRIndicator
from core.indicators.supertrend import SuperTrendIndicator
from core.indicators.volume import OBVIndicator

import pandas as pd


class IndicatorRegistry:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.indicators: dict[str, BaseIndicator] = {}
        self.results: dict[str, dict] = {}

        indicator_configs = config.get("indicators", {})

        indicator_classes = {
            "rsi": RSIIndicator,
            "macd": MACDIndicator,
            "bollinger": BollingerIndicator,
            "ema": EMAIndicator,
            "kdj": KDJIndicator,
            "atr": ATRIndicator,
            "supertrend": SuperTrendIndicator,
            "obv": OBVIndicator,
        }

        for name, cls in indicator_classes.items():
            cfg = indicator_configs.get(name, {})
            if cfg.get("enabled", False):
                self.indicators[name] = cls(cfg)
                self.logger.info(f"已加载指标: {name}")

    def calculate_all(self, key: str, df: pd.DataFrame):
        self.results[key] = {}
        for name, indicator in self.indicators.items():
            try:
                result = indicator.calculate(df)
                self.results[key][name] = result
            except Exception as e:
                self.logger.error(f"计算指标 {name} 失败 ({key}): {e}")

    def get_all_signals(self, key: str, df: pd.DataFrame) -> list:
        all_signals = []
        for name, indicator in self.indicators.items():
            result = self.results.get(key, {}).get(name)
            if result is None:
                continue
            try:
                signals = indicator.get_signals(df, result)
                all_signals.extend(signals)
            except Exception as e:
                self.logger.error(f"获取信号 {name} 失败 ({key}): {e}")
        return all_signals

    def get_result(self, key: str, indicator_name: str) -> dict:
        return self.results.get(key, {}).get(indicator_name, {})

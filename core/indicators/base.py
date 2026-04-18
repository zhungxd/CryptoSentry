from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class Signal:
    indicator_name: str
    signal_type: str
    strength: str
    description: str
    value: Optional[dict] = None


class BaseIndicator(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> dict:
        pass

    @abstractmethod
    def get_signals(self, df: pd.DataFrame, result: dict) -> list[Signal]:
        pass

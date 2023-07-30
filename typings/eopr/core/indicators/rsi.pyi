"""
This type stub file was generated by pyright.
"""

import typing
import pydantic
from eopr.core.indicators.common import CandlePrice, FloatArray, TrendAnalysis

RSIValues = FloatArray
Interpretation = str
class RSIParameters(pydantic.BaseModel):
    prices: list[CandlePrice]
    period: int
    err_handler: typing.Callable[[Exception], None] = ...


class RSIIndicator(pydantic.BaseModel):
    rsi_values: RSIValues
    overbought: float
    oversold: float
    analysis: TrendAnalysis
    err_handler: typing.Callable[[Exception], None] = ...


def rsi(rsi_params: RSIParameters) -> RSIIndicator:
    ...

def interpret_rsi(rsi_indicator: RSIIndicator) -> RSIIndicator:
    ...

"""
This type stub file was generated by pyright.
"""

import pydantic

FloatArray = list[float]
CandlePrice = FloatArray
class TrendAnalysis(pydantic.BaseModel):
    bullish: bool
    bearish: bool
    interpretation: str = ...


"""SMA, Bollinger Bands and %B. Close-only, vectorised, timeframe-agnostic.

These functions know nothing about daily vs weekly. The caller hands them a close
series already on the timeframe it wants, which is what keeps the weekly numbers
honest -- they are computed from weekly bars, never sampled from daily output.
"""
from __future__ import annotations

from typing import NamedTuple

import pandas as pd


class Bands(NamedTuple):
    mid: pd.Series
    upper: pd.Series
    lower: pd.Series
    sigma: pd.Series


def sma(close: pd.Series, period: int) -> pd.Series:
    """Simple moving average. NaN until `period` bars are available."""
    return close.rolling(period, min_periods=period).mean()


def bollinger(close: pd.Series, period: int, stddev: float, ddof: int) -> Bands:
    """Bollinger bands on close.

    `ddof` is explicit because it is a silent correctness trap: pandas defaults to
    the sample standard deviation (ddof=1) while every charting package computes
    Bollinger bands with the population standard deviation (ddof=0).
    """
    mid = close.rolling(period, min_periods=period).mean()
    sigma = close.rolling(period, min_periods=period).std(ddof=ddof)
    return Bands(mid=mid, upper=mid + stddev * sigma, lower=mid - stddev * sigma, sigma=sigma)


def percent_b(close: pd.Series, upper: pd.Series, lower: pd.Series) -> pd.Series:
    """(close - lower) / (upper - lower).

    Returns NaN where the band has zero width -- a halted or fixed-price
    instrument, where every close in the window is identical. The caller maps
    that NaN to NEUTRAL. There is no division by zero on any path.
    """
    width = upper - lower
    return (close - lower).divide(width.where(width > 0))

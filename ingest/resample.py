"""Daily close series -> weekly (W-FRI) close series.

The weekly timeframe exists as real bars, not as a stride over daily output. Every
weekly indicator downstream is computed from what this module returns.
"""
from __future__ import annotations

import pandas as pd

WEEKLY_RULE = "W-FRI"


def to_weekly(close: pd.Series) -> pd.Series:
    """Resample a daily close series to weekly bars labelled by week-ending Friday.

    Semantics worth stating, because they show up in the UI:

    * The bar's value is the last close *available* in that week, so a Friday
      holiday transparently falls back to Thursday.
    * The current, in-progress week produces a bar. Mid-week that bar carries
      today's close and is labelled with a Friday that has not happened yet. This
      is deliberate -- it is the live weekly signal -- but it means a weekly
      signal can flip and unflip before the week actually closes.
    * Weeks with no trading at all are dropped rather than emitted as NaN.
    """
    if not isinstance(close.index, pd.DatetimeIndex):
        raise TypeError("to_weekly requires a DatetimeIndex")
    if close.empty:
        return close.astype(float)

    weekly = close.resample(WEEKLY_RULE).last()
    return weekly.dropna()

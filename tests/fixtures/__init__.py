"""Hand-constructed close series with exactly known indicator values.

Every series is built so the final 20-bar Bollinger window contains ten bars at
one value and ten at another. That makes the mean and the *population* standard
deviation exact integers, computable on paper:

    window = [104] * 10 + [96] * 10
    mid    = 100
    sigma  = sqrt(((+4)^2 * 10 + (-4)^2 * 10) / 20) = 4
    upper  = 100 + 2*4 = 108
    lower  = 100 - 2*4 =  92
    width  = 16

The 30 bars before that window are then chosen to land SMA50 on a specific
integer, with no float rounding anywhere. Ten leading pad bars bring the series
to 60 so it clears min_bars; they sit outside the 50-bar window and so cannot
affect any asserted value.
"""
from __future__ import annotations

from typing import List, Sequence

import pandas as pd

# The band window every fixture ends with, and its hand-computed values.
BAND_MID = 100.0
BAND_SIGMA = 4.0
BAND_UPPER = 108.0
BAND_LOWER = 92.0
BAND_WIDTH = 16.0

WINDOW_ENDING_LOW = [104.0] * 10 + [96.0] * 10   # last close 96 -> pct_b 0.25
WINDOW_ENDING_HIGH = [96.0] * 10 + [104.0] * 10  # last close 104 -> pct_b 0.75


def as_series(values: Sequence[float], start: str = "2024-01-01") -> pd.Series:
    """Attach a business-day index. Calendar dates are irrelevant to these tests."""
    idx = pd.bdate_range(start=start, periods=len(values))
    return pd.Series([float(v) for v in values], index=idx, name="close")


def build(prefix_30: List[float], window_20: List[float], pad: float = 90.0) -> pd.Series:
    """10 pad bars + 30 bars setting SMA50 + the 20-bar band window = 60 bars."""
    assert len(prefix_30) == 30, "the 50-bar window is 30 bars plus the 20-bar band"
    assert len(window_20) == 20
    return as_series([pad] * 10 + prefix_30 + window_20)


# --- Case A: BULLISH, exactly on the pct_b <= 0.25 boundary ------------------
# SMA50 = (20*90 + 10*95 + 10*104 + 10*96) / 50 = 4750 / 50 = 95
# close 96 > SMA50 95, close 96 > lower 92, pct_b = (96-92)/16 = 0.25
BULLISH_SERIES = build([90.0] * 20 + [95.0] * 10, WINDOW_ENDING_LOW)
BULLISH_SMA50 = 95.0

# --- Case B: same final bar, NEUTRAL because the 50 is too close -------------
# SMA50 = (20*90 + 10*105 + 10*104 + 10*96) / 50 = 4850 / 50 = 97
# close 96 < SMA50 97. Note SMA20 - sigma = 96, and 97 is not below it.
NEUTRAL_TREND_SERIES = build([90.0] * 20 + [105.0] * 10, WINDOW_ENDING_LOW)
NEUTRAL_TREND_SMA50 = 97.0

# --- Case D: BEARISH, exactly on the pct_b >= 0.75 boundary ------------------
# SMA50 = (20*110 + 10*105 + 10*96 + 10*104) / 50 = 5250 / 50 = 105
# close 104 < SMA50 105, close 104 < upper 108, pct_b = (104-92)/16 = 0.75
BEARISH_SERIES = build([110.0] * 20 + [105.0] * 10, WINDOW_ENDING_HIGH, pad=110.0)
BEARISH_SMA50 = 105.0

# --- Case C: broken below the lower band -------------------------------------
# A hard uptrend, then a crash that stays above the far-behind 50 but punches
# clean through the lower band. close > SMA50 holds and pct_b <= 0.25 holds, so
# only the `close > lower` clause stops this being called BULLISH.
BREAKDOWN_SERIES = as_series([50.0] * 40 + [100.0] * 19 + [88.0])

# --- Case E: zero-width band --------------------------------------------------
FLAT_SERIES = as_series([100.0] * 60)

# --- Case F: one bar short of min_bars ----------------------------------------
SHORT_SERIES = BULLISH_SERIES.iloc[:59]


def random_walk(n: int = 1500, seed: int = 42, vol: float = 0.015) -> pd.Series:
    """A deterministic lognormal walk.

    Not a hand-computed fixture -- it exists purely to exercise the classifier
    over a series with realistic variety, for the comparative and hit-rate tests
    where the question is "how often" rather than "what exactly".
    """
    import numpy as np

    rng = np.random.default_rng(seed)
    path = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, vol, n)))
    return as_series(path)


RANDOM_WALK_SERIES = random_walk()

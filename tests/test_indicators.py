"""Indicator maths against hand-computed values. No network, no yfinance."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from ingest.indicators import bollinger, percent_b, sma
from tests import fixtures as fx


def test_sma_is_nan_until_the_window_is_full():
    s = fx.as_series(list(range(1, 11)))
    out = sma(s, 5)
    assert out.iloc[:4].isna().all()
    # bars 1..5 -> mean 3
    assert out.iloc[4] == pytest.approx(3.0)
    # bars 6..10 -> mean 8
    assert out.iloc[-1] == pytest.approx(8.0)


def test_bollinger_matches_the_hand_computed_window():
    """window = [104]*10 + [96]*10 -> mid 100, sigma 4, band 92..108."""
    bands = bollinger(fx.BULLISH_SERIES, period=20, stddev=2.0, ddof=0)
    assert bands.mid.iloc[-1] == pytest.approx(fx.BAND_MID)
    assert bands.sigma.iloc[-1] == pytest.approx(fx.BAND_SIGMA)
    assert bands.upper.iloc[-1] == pytest.approx(fx.BAND_UPPER)
    assert bands.lower.iloc[-1] == pytest.approx(fx.BAND_LOWER)


def test_population_and_sample_stddev_actually_differ():
    """Guards the ddof choice. If this ever passes with ddof unset, someone has
    changed the default and every band in the app has quietly moved."""
    pop = bollinger(fx.BULLISH_SERIES, 20, 2.0, ddof=0)
    sample = bollinger(fx.BULLISH_SERIES, 20, 2.0, ddof=1)
    assert pop.sigma.iloc[-1] == pytest.approx(4.0)
    # sqrt(20/19) * 4
    assert sample.sigma.iloc[-1] == pytest.approx(4.0 * math.sqrt(20 / 19))
    assert pop.upper.iloc[-1] < sample.upper.iloc[-1]


def test_percent_b_at_the_hand_computed_boundaries():
    bands = bollinger(fx.BULLISH_SERIES, 20, 2.0, 0)
    pb = percent_b(fx.BULLISH_SERIES, bands.upper, bands.lower)
    # (96 - 92) / 16
    assert pb.iloc[-1] == pytest.approx(0.25)

    bands = bollinger(fx.BEARISH_SERIES, 20, 2.0, 0)
    pb = percent_b(fx.BEARISH_SERIES, bands.upper, bands.lower)
    # (104 - 92) / 16
    assert pb.iloc[-1] == pytest.approx(0.75)


def test_percent_b_goes_negative_below_the_lower_band():
    bands = bollinger(fx.BREAKDOWN_SERIES, 20, 2.0, 0)
    pb = percent_b(fx.BREAKDOWN_SERIES, bands.upper, bands.lower)
    assert pb.iloc[-1] < 0


def test_percent_b_on_a_zero_width_band_is_nan_not_a_crash():
    bands = bollinger(fx.FLAT_SERIES, 20, 2.0, 0)
    assert bands.upper.iloc[-1] == bands.lower.iloc[-1]
    pb = percent_b(fx.FLAT_SERIES, bands.upper, bands.lower)
    assert pd.isna(pb.iloc[-1])
    assert not pb.isin([math.inf, -math.inf]).any()

"""Classification against the worked example, plus the structural invariant."""
from __future__ import annotations

import pandas as pd
import pytest

from ingest.config import SignalConfig
from ingest.signals import (
    BEARISH,
    BULLISH,
    INSUFFICIENT_DATA,
    NEUTRAL,
    changed,
    classify,
    latest_state,
)
from tests import fixtures as fx

CFG = SignalConfig(
    bb_period=20, bb_stddev=2.0, bb_ddof=0, sma_period=50, min_bars=60, zone_pct=0.25
)


def last_signal(series) -> str:
    return classify(series, CFG)["signal"].iloc[-1]


# --- the four cases from the worked example ---------------------------------

def test_case_a_bullish_on_the_boundary():
    frame = classify(fx.BULLISH_SERIES, CFG)
    row = frame.iloc[-1]
    assert row["close"] == pytest.approx(96.0)
    assert row["sma50"] == pytest.approx(fx.BULLISH_SMA50)   # 95
    assert row["lower"] == pytest.approx(fx.BAND_LOWER)      # 92
    assert row["pct_b"] == pytest.approx(0.25)               # exactly on the edge
    assert row["signal"] == BULLISH


def test_case_b_same_bar_neutral_when_the_fifty_is_too_close():
    frame = classify(fx.NEUTRAL_TREND_SERIES, CFG)
    row = frame.iloc[-1]
    assert row["close"] == pytest.approx(96.0)
    assert row["sma50"] == pytest.approx(fx.NEUTRAL_TREND_SMA50)  # 97
    assert row["pct_b"] == pytest.approx(0.25)                    # band test passes
    assert row["close"] < row["sma50"]                            # trend test fails
    assert row["signal"] == NEUTRAL


def test_case_c_breakdown_below_the_band_is_not_bullish():
    """Isolates the `close > lower` clause: every other bullish condition holds."""
    frame = classify(fx.BREAKDOWN_SERIES, CFG)
    row = frame.iloc[-1]
    assert row["close"] > row["sma50"]        # trend test passes
    assert row["pct_b"] <= CFG.zone_pct       # band test passes
    assert row["close"] < row["lower"]        # ...but price is through the band
    assert row["pct_b"] < 0
    assert row["signal"] == NEUTRAL


def test_case_d_bearish_on_the_boundary():
    frame = classify(fx.BEARISH_SERIES, CFG)
    row = frame.iloc[-1]
    assert row["close"] == pytest.approx(104.0)
    assert row["sma50"] == pytest.approx(fx.BEARISH_SMA50)   # 105
    assert row["upper"] == pytest.approx(fx.BAND_UPPER)      # 108
    assert row["pct_b"] == pytest.approx(0.75)
    assert row["signal"] == BEARISH


def test_case_e_zero_width_band_is_neutral_not_insufficient():
    frame = classify(fx.FLAT_SERIES, CFG)
    row = frame.iloc[-1]
    assert pd.isna(row["pct_b"])
    assert row["signal"] == NEUTRAL


def test_case_f_short_history_is_insufficient_data():
    assert len(fx.SHORT_SERIES) == 59
    assert last_signal(fx.SHORT_SERIES) == INSUFFICIENT_DATA
    # ...and the very next bar, the 60th, is scoreable.
    assert last_signal(fx.BULLISH_SERIES) == BULLISH


def test_bar_59_of_a_full_series_is_still_insufficient():
    frame = classify(fx.BULLISH_SERIES, CFG)
    assert frame["signal"].iloc[-2] == INSUFFICIENT_DATA
    assert frame["signal"].iloc[-1] == BULLISH


# --- symmetry and the structural invariant ----------------------------------

def test_bullish_and_bearish_zones_are_symmetric():
    assert CFG.upper_zone == pytest.approx(1.0 - CFG.zone_pct)


def test_bullish_bars_always_have_sma50_more_than_one_sigma_below_sma20():
    """The reason only a sliver of the universe ever fires.

    pct_b <= 0.25 means close <= mid - sigma, and close > sma50, therefore
    sma50 < mid - sigma. Asserted over every bar of every fixture rather than
    trusted as algebra.
    """
    margin = 2.0 - 4.0 * CFG.zone_pct  # = 1 sigma at zone_pct 0.25
    slack = 1e-6                       # absorbs ZONE_EPSILON, nothing more
    for series in (
        fx.BULLISH_SERIES,
        fx.BEARISH_SERIES,
        fx.NEUTRAL_TREND_SERIES,
        fx.BREAKDOWN_SERIES,
        fx.FLAT_SERIES,
        fx.RANDOM_WALK_SERIES,
    ):
        frame = classify(series, CFG)
        bull = frame[frame["signal"] == BULLISH]
        assert (bull["sma50"] < bull["mid"] - margin * bull["sigma"] + slack).all()

        bear = frame[frame["signal"] == BEARISH]
        assert (bear["sma50"] > bear["mid"] + margin * bear["sigma"] - slack).all()


def fired(series, cfg) -> float:
    """Share of scoreable bars carrying a signal."""
    sig = classify(series, cfg)["signal"]
    scoreable = sig[sig != INSUFFICIENT_DATA]
    return scoreable.isin([BULLISH, BEARISH]).mean()


def test_loosening_zone_pct_makes_the_signal_far_more_common():
    """A guard on the knob: 0.45 is not 'slightly wider than' 0.25."""
    loose = SignalConfig(
        bb_period=20, bb_stddev=2.0, bb_ddof=0, sma_period=50, min_bars=60, zone_pct=0.45
    )
    assert fired(fx.RANDOM_WALK_SERIES, loose) > 3 * fired(fx.RANDOM_WALK_SERIES, CFG)


def test_hit_rate_stays_in_the_low_single_digits():
    """The sanity check that would have caught a broken implementation.

    If a third of bars fire, the maths is wrong -- most likely zone_pct applied
    to the wrong side, or the SMA50 trend filter dropped.
    """
    rate = fired(fx.RANDOM_WALK_SERIES, CFG)
    assert 0.0 < rate < 0.10, f"{rate:.1%} of bars fired; expected low single digits"


# --- latest_state / changed --------------------------------------------------

def test_latest_state_reports_the_previous_bars_own_classification():
    state = latest_state(classify(fx.BULLISH_SERIES, CFG))
    assert state["signal"] == BULLISH
    assert state["prev_signal"] == INSUFFICIENT_DATA
    assert state["close"] == pytest.approx(96.0)
    assert state["sma50"] == pytest.approx(95.0)
    assert state["pct_b"] == pytest.approx(0.25)
    assert state["bar_date"] == fx.BULLISH_SERIES.index[-1].date().isoformat()


def test_latest_state_emits_null_not_nan_for_an_unscoreable_bar():
    state = latest_state(classify(fx.FLAT_SERIES, CFG))
    assert state["pct_b"] is None
    assert state["signal"] == NEUTRAL


def test_latest_state_on_an_empty_frame():
    state = latest_state(classify(pd.Series(dtype=float), CFG))
    assert state["signal"] == INSUFFICIENT_DATA
    assert state["bar_date"] is None


@pytest.mark.parametrize(
    "signal,prev,expected",
    [
        (BULLISH, NEUTRAL, True),
        (NEUTRAL, BEARISH, True),
        (BULLISH, BULLISH, False),
        # crossing the history threshold is a data event, not a market event
        (BULLISH, INSUFFICIENT_DATA, False),
        (INSUFFICIENT_DATA, NEUTRAL, False),
    ],
)
def test_changed_today(signal, prev, expected):
    assert changed(signal, prev) is expected

"""Weekly bars are real bars, not every fifth daily bar."""
from __future__ import annotations

import pandas as pd
import pytest

from ingest.config import SignalConfig
from ingest.indicators import sma
from ingest.resample import to_weekly

CFG = SignalConfig(
    bb_period=20, bb_stddev=2.0, bb_ddof=0, sma_period=50, min_bars=60, zone_pct=0.25
)


def daily(dates, values) -> pd.Series:
    return pd.Series([float(v) for v in values], index=pd.DatetimeIndex(dates), name="close")


def test_weekly_bars_are_labelled_by_week_ending_friday():
    # Mon 2024-01-01 .. Wed 2024-01-17, business days only.
    idx = pd.bdate_range("2024-01-01", "2024-01-17")
    s = pd.Series(range(len(idx)), index=idx, dtype=float)
    w = to_weekly(s)

    assert [d.date().isoformat() for d in w.index] == [
        "2024-01-05",
        "2024-01-12",
        "2024-01-19",
    ]


def test_each_weekly_bar_takes_the_last_close_of_its_week():
    idx = pd.bdate_range("2024-01-01", "2024-01-12")
    s = pd.Series(range(len(idx)), index=idx, dtype=float)
    w = to_weekly(s)
    assert w.loc["2024-01-05"] == s.loc["2024-01-05"]   # Friday
    assert w.loc["2024-01-12"] == s.loc["2024-01-12"]


def test_a_friday_holiday_falls_back_to_the_last_traded_day():
    # Good Friday 2024-03-29 is a holiday in Paris, Frankfurt and New York.
    dates = ["2024-03-25", "2024-03-26", "2024-03-27", "2024-03-28"]
    s = daily(dates, [10, 11, 12, 13])
    w = to_weekly(s)
    assert len(w) == 1
    assert w.index[0].date().isoformat() == "2024-03-29"  # labelled Friday
    assert w.iloc[0] == 13.0                              # valued Thursday


def test_the_in_progress_week_produces_a_bar_labelled_with_a_future_friday():
    idx = pd.bdate_range("2024-01-01", "2024-01-17")  # ends Wednesday
    s = pd.Series(range(len(idx)), index=idx, dtype=float)
    w = to_weekly(s)
    assert w.index[-1] > s.index[-1]
    assert w.iloc[-1] == s.iloc[-1]


def test_weeks_with_no_trading_are_dropped_not_emitted_as_nan():
    s = daily(["2024-01-03", "2024-01-24"], [10, 20])  # a three-week gap
    w = to_weekly(s)
    assert len(w) == 2
    assert not w.isna().any()


def test_weekly_sma_is_not_the_daily_sma_sampled_weekly():
    """The whole reason this module exists.

    A 50-period SMA on weekly bars spans a year. Taking a 50-day SMA and reading
    it every Friday spans ten weeks. These are different numbers and confusing
    them would make every weekly signal wrong.
    """
    idx = pd.bdate_range("2020-01-01", periods=600)
    s = pd.Series(range(len(idx)), index=idx, dtype=float)

    weekly_sma = sma(to_weekly(s), CFG.sma_period)
    daily_sma_sampled_weekly = to_weekly(sma(s, CFG.sma_period))

    aligned = pd.concat([weekly_sma, daily_sma_sampled_weekly], axis=1).dropna()
    assert not aligned.empty
    assert (aligned.iloc[:, 0] != aligned.iloc[:, 1]).all()


def test_to_weekly_rejects_a_non_datetime_index():
    with pytest.raises(TypeError):
        to_weekly(pd.Series([1.0, 2.0]))


def test_to_weekly_of_an_empty_series_is_empty():
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    assert to_weekly(empty).empty

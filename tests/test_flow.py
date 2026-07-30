"""Relative strength and breadth arithmetic, against hand-computed values."""
from __future__ import annotations

import pandas as pd
import pytest

from ingest.flow import ALL, GEO_COLUMNS, build_flow, compute_returns, horizon_return
from ingest.sectors_map import GICS_SECTORS
from ingest.signals import BEARISH, BULLISH, NEUTRAL
from ingest.symbols import FRANCE, GERMANY, US
from tests.test_universe import Constituent

HORIZONS = {"1w": 7, "1m": 30}


def series(pairs) -> pd.Series:
    dates, values = zip(*pairs)
    return pd.Series([float(v) for v in values], index=pd.DatetimeIndex(dates))


def stock(symbol, sector, geography) -> Constituent:
    return Constituent(
        symbol=symbol,
        yahoo_symbol=symbol,
        name=symbol,
        index="SP500",
        geography=geography,
        sector_raw=sector,
        sector=sector,
    )


# --- horizon_return ----------------------------------------------------------

def test_horizon_return_is_calendar_anchored():
    s = series([("2026-01-01", 100), ("2026-01-15", 110), ("2026-01-22", 120)])
    as_of = pd.Timestamp("2026-01-22")
    # 7 days back from the 22nd is the 15th: 120/110 - 1
    assert horizon_return(s, as_of, 7) == pytest.approx(120 / 110 - 1)


def test_horizon_return_uses_the_last_bar_at_or_before_the_anchor():
    """A market closed on the anchor date must reach back, not return None. This
    is what keeps a Paris window aligned with a New York one."""
    s = series([("2026-01-05", 100), ("2026-01-20", 130)])
    # 7 days before the 20th is the 13th; nothing traded then, so the 5th is used.
    assert horizon_return(s, pd.Timestamp("2026-01-20"), 7) == pytest.approx(0.30)


def test_horizon_return_is_none_when_history_is_too_short():
    s = series([("2026-01-20", 100), ("2026-01-22", 110)])
    assert horizon_return(s, pd.Timestamp("2026-01-22"), 30) is None


def test_horizon_return_on_an_empty_series():
    assert horizon_return(pd.Series(dtype=float), pd.Timestamp("2026-01-01"), 7) is None


# --- relative strength -------------------------------------------------------

def test_relative_strength_is_the_cell_mean_minus_the_geography_mean():
    """Two US tech names at +10% and +20%, two US energy names at 0% and -10%.
    Geography mean = +5%. Tech cell = +15% mean -> +10% relative.
    Equal-weight, so the cell mean is unaffected by any notion of size."""
    as_of = pd.Timestamp("2026-02-01")
    closes = {
        "T1": series([("2026-01-01", 100), ("2026-02-01", 110)]),
        "T2": series([("2026-01-01", 100), ("2026-02-01", 120)]),
        "E1": series([("2026-01-01", 100), ("2026-02-01", 100)]),
        "E2": series([("2026-01-01", 100), ("2026-02-01", 90)]),
    }
    constituents = [
        stock("T1", "Information Technology", US),
        stock("T2", "Information Technology", US),
        stock("E1", "Energy", US),
        stock("E2", "Energy", US),
    ]
    returns = compute_returns(closes, as_of, {"1m": 30})
    cells, baselines = build_flow(constituents, returns, {}, {"1m": 30})

    us_baseline = next(b for b in baselines if b["geography"] == US)
    assert us_baseline["ret_1m"] == pytest.approx(0.05)

    tech = next(c for c in cells if c["sector"] == "Information Technology" and c["geography"] == US)
    assert tech["rel_1m"] == pytest.approx(0.10)
    energy = next(c for c in cells if c["sector"] == "Energy" and c["geography"] == US)
    assert energy["rel_1m"] == pytest.approx(-0.10)


def test_relative_strength_sums_to_zero_across_a_geography():
    """A weighted identity worth asserting: relative strength is a deviation from
    the mean, so the constituent-weighted deviations must cancel."""
    as_of = pd.Timestamp("2026-02-01")
    closes = {
        s: series([("2026-01-01", 100), ("2026-02-01", 100 + i * 5)])
        for i, s in enumerate(["A", "B", "C", "D"])
    }
    constituents = [
        stock("A", "Energy", US),
        stock("B", "Energy", US),
        stock("C", "Utilities", US),
        stock("D", "Utilities", US),
    ]
    returns = compute_returns(closes, as_of, {"1m": 30})
    cells, _ = build_flow(constituents, returns, {}, {"1m": 30})

    total = sum(c["rel_1m"] * c["n"] for c in cells if c["geography"] == US and c["rel_1m"])
    assert total == pytest.approx(0.0, abs=1e-9)


def test_the_all_column_pools_constituents_across_geographies():
    as_of = pd.Timestamp("2026-02-01")
    closes = {
        "US1": series([("2026-01-01", 100), ("2026-02-01", 110)]),
        "FR1": series([("2026-01-01", 100), ("2026-02-01", 130)]),
        "DE1": series([("2026-01-01", 100), ("2026-02-01", 90)]),
    }
    constituents = [
        stock("US1", "Energy", US),
        stock("FR1", "Energy", FRANCE),
        stock("DE1", "Utilities", GERMANY),
    ]
    returns = compute_returns(closes, as_of, {"1m": 30})
    cells, baselines = build_flow(constituents, returns, {}, {"1m": 30})

    all_baseline = next(b for b in baselines if b["geography"] == ALL)
    assert all_baseline["n"] == 3
    assert all_baseline["ret_1m"] == pytest.approx((0.10 + 0.30 - 0.10) / 3)

    energy_all = next(c for c in cells if c["sector"] == "Energy" and c["geography"] == ALL)
    assert energy_all["n"] == 2
    assert energy_all["rel_1m"] == pytest.approx(0.20 - 0.10)


def test_every_sector_geography_cell_is_emitted_even_when_empty():
    """Empty and thin cells are information. A missing cell and a genuinely empty
    one are different facts and the grid has to be able to tell them apart."""
    as_of = pd.Timestamp("2026-02-01")
    closes = {"A": series([("2026-01-01", 100), ("2026-02-01", 110)])}
    cells, _ = build_flow([stock("A", "Energy", US)], compute_returns(closes, as_of, HORIZONS), {}, HORIZONS)

    assert len(cells) == len(GICS_SECTORS) * len(GEO_COLUMNS) == 44
    empty = next(c for c in cells if c["sector"] == "Utilities" and c["geography"] == GERMANY)
    assert empty["n"] == 0
    assert empty["rel_1w"] is None and empty["rel_1m"] is None


def test_a_symbol_without_enough_history_is_skipped_not_counted_as_zero():
    """Treating missing history as a 0% return would drag every mean toward zero."""
    as_of = pd.Timestamp("2026-02-01")
    closes = {
        "OLD": series([("2026-01-01", 100), ("2026-02-01", 120)]),
        "NEW": series([("2026-01-31", 100), ("2026-02-01", 101)]),
    }
    constituents = [stock("OLD", "Energy", US), stock("NEW", "Energy", US)]
    returns = compute_returns(closes, as_of, {"1m": 30})
    assert returns["NEW"]["1m"] is None

    _, baselines = build_flow(constituents, returns, {}, {"1m": 30})
    us = next(b for b in baselines if b["geography"] == US)
    assert us["n"] == 2                              # both are constituents
    assert us["ret_1m"] == pytest.approx(0.20)       # but only one has a return


def test_unmapped_sector_constituents_are_excluded_from_the_arithmetic():
    as_of = pd.Timestamp("2026-02-01")
    closes = {"A": series([("2026-01-01", 100), ("2026-02-01", 110)])}
    orphan = Constituent("A", "A", "A", "SP500", US, "Blockchain", None)
    cells, baselines = build_flow([orphan], compute_returns(closes, as_of, {"1m": 30}), {}, {"1m": 30})
    assert all(c["n"] == 0 for c in cells)
    assert next(b for b in baselines if b["geography"] == US)["n"] == 0


# --- breadth -----------------------------------------------------------------

def test_breadth_counts_the_daily_signal_within_each_cell():
    as_of = pd.Timestamp("2026-02-01")
    symbols = ["A", "B", "C", "D"]
    closes = {s: series([("2026-01-01", 100), ("2026-02-01", 110)]) for s in symbols}
    constituents = [stock(s, "Energy", US) for s in symbols]
    signals = {"A": BULLISH, "B": BULLISH, "C": BEARISH, "D": NEUTRAL}

    cells, _ = build_flow(
        constituents, compute_returns(closes, as_of, {"1m": 30}), signals, {"1m": 30}
    )
    cell = next(c for c in cells if c["sector"] == "Energy" and c["geography"] == US)
    assert cell["n"] == 4
    assert cell["breadth"] == {"bullish": 2, "bearish": 1, "neutral": 1, "insufficient": 0}


def test_a_symbol_with_no_signal_at_all_counts_as_insufficient():
    as_of = pd.Timestamp("2026-02-01")
    closes = {"A": series([("2026-01-01", 100), ("2026-02-01", 110)])}
    cells, _ = build_flow(
        [stock("A", "Energy", US)], compute_returns(closes, as_of, {"1m": 30}), {}, {"1m": 30}
    )
    cell = next(c for c in cells if c["sector"] == "Energy" and c["geography"] == US)
    assert cell["breadth"]["insufficient"] == 1

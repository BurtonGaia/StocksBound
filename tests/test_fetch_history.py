"""Batching, retry, and the incremental cache. yfinance fully stubbed."""
from __future__ import annotations

import pandas as pd
import pytest

from ingest import fetch as F
from ingest import history as H
from ingest.config import UniverseConfig

CFG = UniverseConfig(history_years=10, batch_size=2, max_retries=3, backoff_base_s=0.0)


def wide(dates, data: dict) -> pd.DataFrame:
    """A yfinance-shaped frame: MultiIndex (ticker, field) columns."""
    idx = pd.DatetimeIndex(dates)
    frames = {}
    for ticker, closes in data.items():
        frames[(ticker, "Close")] = pd.Series(closes, index=idx, dtype=float)
    out = pd.DataFrame(frames)
    out.columns = pd.MultiIndex.from_tuples(out.columns)
    return out


# --- batching and failure handling -------------------------------------------

def test_chunks():
    assert F.chunks(["a", "b", "c", "d", "e"], 2) == [["a", "b"], ["c", "d"], ["e"]]


def test_fetch_splits_into_batches(monkeypatch):
    seen = []

    def fake(tickers, period, timeout=60):
        seen.append(list(tickers))
        return wide(["2026-01-01"], {t: [10.0] for t in tickers})

    monkeypatch.setattr(F, "_download", fake)
    closes, failed = F.fetch_closes(["A", "B", "C"], "1y", CFG)
    assert seen == [["A", "B"], ["C"]]
    assert set(closes) == {"A", "B", "C"}
    assert failed == []


def test_an_all_nan_column_is_reported_as_failed_not_returned(monkeypatch):
    """A delisted ticker comes back as a NaN column rather than an error. If it
    were passed through, the classifier would see an empty series."""
    def fake(tickers, period, timeout=60):
        return wide(["2026-01-01", "2026-01-02"], {"A": [10.0, 11.0], "DEAD": [float("nan")] * 2})

    monkeypatch.setattr(F, "_download", fake)
    closes, failed = F.fetch_closes(["A", "DEAD"], "1y", CFG)
    assert set(closes) == {"A"}
    assert failed == [("DEAD", "no price data returned")]


def test_a_batch_is_retried_then_gives_up_without_aborting_the_run(monkeypatch):
    calls = {"n": 0}

    def fake(tickers, period, timeout=60):
        calls["n"] += 1
        if "A" in tickers:
            raise RuntimeError("rate limited")
        return wide(["2026-01-01"], {t: [10.0] for t in tickers})

    monkeypatch.setattr(F, "_download", fake)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)

    closes, failed = F.fetch_closes(["A", "B", "C"], "1y", CFG)
    assert calls["n"] == CFG.max_retries + 1          # 3 on the bad batch, 1 on the good
    assert set(closes) == {"C"}                       # the second batch still ran
    assert {t for t, _ in failed} == {"A", "B"}
    assert all("batch download failed" in reason for _, reason in failed)


def test_a_transient_failure_is_recovered_on_retry(monkeypatch):
    calls = {"n": 0}

    def fake(tickers, period, timeout=60):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return wide(["2026-01-01"], {t: [10.0] for t in tickers})

    monkeypatch.setattr(F, "_download", fake)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    closes, failed = F.fetch_closes(["A"], "1y", CFG)
    assert set(closes) == {"A"}
    assert failed == []


def test_extract_close_drops_cross_market_holiday_gaps():
    """The frame index is the union of every market's trading days. An embedded
    NaN makes every rolling window spanning it return NaN, so this drop is
    load-bearing, not tidying."""
    frame = wide(
        ["2026-01-01", "2026-01-02", "2026-01-05"],
        {"US1": [10.0, 11.0, 12.0], "FR1": [20.0, float("nan"), 22.0]},
    )
    out = F._extract_close(frame, ["US1", "FR1"])
    assert len(out["US1"]) == 3
    assert len(out["FR1"]) == 2
    assert not out["FR1"].isna().any()


def test_extract_close_normalises_the_index_and_sorts():
    frame = wide(["2026-01-05", "2026-01-02"], {"A": [12.0, 11.0]})
    out = F._extract_close(frame, ["A"])["A"]
    assert out.index.is_monotonic_increasing
    assert out.index.tz is None


# --- the cache ---------------------------------------------------------------

def test_merge_prefers_fresh_values_on_overlap():
    """Adjusted closes are restated on every dividend. Preferring cached values
    would splice two adjustment bases together and put a step through the series."""
    cached = pd.DataFrame({"A": [10.0, 11.0]}, index=pd.DatetimeIndex(["2026-01-01", "2026-01-02"]))
    fresh = pd.DataFrame({"A": [11.5, 12.0]}, index=pd.DatetimeIndex(["2026-01-02", "2026-01-03"]))
    merged = H.merge(cached, fresh)
    assert list(merged["A"]) == [10.0, 11.5, 12.0]


def test_merge_unions_symbols():
    cached = pd.DataFrame({"A": [10.0]}, index=pd.DatetimeIndex(["2026-01-01"]))
    fresh = pd.DataFrame({"B": [20.0]}, index=pd.DatetimeIndex(["2026-01-01"]))
    assert set(H.merge(cached, fresh).columns) == {"A", "B"}


def test_merge_handles_either_side_empty():
    frame = pd.DataFrame({"A": [10.0]}, index=pd.DatetimeIndex(["2026-01-01"]))
    assert H.merge(pd.DataFrame(), frame).equals(frame)
    assert H.merge(frame, pd.DataFrame()).equals(frame)


def test_trim_bounds_history_and_drops_untracked_symbols():
    idx = pd.date_range("2010-01-01", "2026-01-01", freq="D")
    frame = pd.DataFrame({"A": 1.0, "B": 2.0}, index=idx)
    trimmed = H.trim(frame, years=2, keep_symbols=["A"])
    assert list(trimmed.columns) == ["A"]
    assert trimmed.index.min() >= pd.Timestamp("2023-12-01")


def test_split_by_coverage_backfills_new_and_short_symbols():
    idx = pd.date_range("2026-01-01", periods=100, freq="D")
    cached = pd.DataFrame({"LONG": 1.0, "SHORT": [1.0] * 10 + [float("nan")] * 90}, index=idx)
    backfill, update = H.split_by_coverage(cached, ["LONG", "SHORT", "BRAND_NEW"], min_bars=60)
    assert update == ["LONG"]
    assert set(backfill) == {"SHORT", "BRAND_NEW"}


def test_split_by_coverage_with_an_empty_cache_backfills_everything():
    backfill, update = H.split_by_coverage(pd.DataFrame(), ["A", "B"], min_bars=60)
    assert backfill == ["A", "B"] and update == []


def test_a_missing_cache_loads_as_empty_rather_than_raising(tmp_path):
    assert H.load(tmp_path / "nope.csv.gz").empty


def test_a_corrupt_cache_loads_as_empty_rather_than_raising(tmp_path):
    """A bad cache must trigger a backfill, not a red build."""
    path = tmp_path / "bad.csv.gz"
    path.write_bytes(b"this is not gzipped csv")
    assert H.load(path).empty


def test_save_then_load_round_trips(tmp_path):
    idx = pd.DatetimeIndex(["2026-01-01", "2026-01-02"])
    frame = pd.DataFrame({"A": [10.5, 11.25], "B": [20.0, 21.0]}, index=idx)
    path = tmp_path / "c.csv.gz"
    H.save(path, frame)
    loaded = H.load(path)
    pd.testing.assert_frame_equal(loaded, frame, check_freq=False)

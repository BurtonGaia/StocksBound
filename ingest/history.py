"""The daily-close cache that makes the ingest incremental.

Stored as a single gzipped CSV: dates down, symbols across. Deliberately not
parquet -- that would pull in pyarrow, a ~40 MB wheel, to save a few seconds on a
job that runs once a day.

This file lives in the GitHub Actions cache, never in the repo. Committing it
would add ~6 MB per day of history to git, about 1.5 GB a year, to store data that
is reconstructible from a single API call. A cache miss is not a failure: it
triggers a full backfill and self-heals.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional, Sequence

import pandas as pd

log = logging.getLogger(__name__)

CACHE_VERSION = "v1-adjclose"  # bump to invalidate; part of the Actions cache key


def load(path: Path) -> pd.DataFrame:
    """Load the cache, or an empty frame if it is absent or unreadable."""
    if not path.exists():
        log.info("no price cache at %s; a full backfill will run", path)
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path, index_col=0, parse_dates=True, compression="gzip")
        frame.index = pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
        log.info("loaded cache: %d bars x %d symbols", len(frame), frame.shape[1])
        return frame.sort_index()
    except Exception as exc:  # noqa: BLE001 - a corrupt cache must not stop the run
        log.warning("price cache unreadable (%s); falling back to full backfill", exc)
        return pd.DataFrame()


def save(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.sort_index().to_csv(path, compression="gzip", float_format="%.6f")
    log.info("wrote cache: %d bars x %d symbols -> %s", len(frame), frame.shape[1], path)


def to_frame(closes: Dict[str, pd.Series]) -> pd.DataFrame:
    if not closes:
        return pd.DataFrame()
    return pd.DataFrame(closes).sort_index()


def merge(cached: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    """Union of both, with fresh values winning on overlap.

    Fresh wins because adjusted closes are restated: every dividend rewrites the
    whole history by a small factor. Preferring cached values would leave the
    series spliced across two different adjustment bases, putting a step through
    the middle of it.
    """
    if cached.empty:
        return fresh
    if fresh.empty:
        return cached

    combined = fresh.combine_first(cached)
    # combine_first is outer on both axes, so the column order comes back
    # alphabetical rather than as supplied. Sort the index; columns do not matter.
    return combined.sort_index()


def trim(frame: pd.DataFrame, years: int, keep_symbols: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Bound the cache: drop bars older than `years` and symbols we no longer track."""
    if frame.empty:
        return frame

    cutoff = frame.index.max() - pd.Timedelta(days=int(years * 366))
    frame = frame.loc[frame.index >= cutoff]

    if keep_symbols is not None:
        keep = [c for c in frame.columns if c in set(keep_symbols)]
        frame = frame[keep]
    return frame


def split_by_coverage(
    cached: pd.DataFrame, symbols: Sequence[str], min_bars: int
) -> "tuple[list[str], list[str]]":
    """Partition symbols into (needs full backfill, needs incremental top-up).

    A symbol already in the cache with enough bars only needs the recent tail.
    Anything else -- new constituent, or a column too short to classify -- gets the
    full history.
    """
    if cached.empty:
        return list(symbols), []

    backfill, update = [], []
    for symbol in symbols:
        if symbol in cached.columns and cached[symbol].notna().sum() >= min_bars:
            update.append(symbol)
        else:
            backfill.append(symbol)
    return backfill, update

"""Batched price download from Yahoo, with retry and backoff.

Two behaviours matter here and both are load-bearing:

* A batch is retried on transport or rate-limit failure. If it still fails, its
  symbols are recorded as failed and the run continues with the next batch. One
  bad batch never aborts the run.
* A single delisted or renamed ticker does not fail its batch -- Yahoo returns an
  all-NaN column for it. Those are filtered out by `close_frame`, so a dead
  constituent quietly disappears from the universe rather than poisoning it.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Dict, List, Sequence, Tuple

import pandas as pd
import yfinance as yf

from .config import UniverseConfig

log = logging.getLogger(__name__)


def chunks(items: Sequence[str], size: int) -> List[List[str]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def _download(tickers: Sequence[str], period: str, timeout: int = 60) -> pd.DataFrame:
    return yf.download(
        list(tickers),
        period=period,
        interval="1d",
        # Split- and dividend-adjusted. Non-negotiable: an unadjusted series puts a
        # step change through the close on every split, which manufactures a
        # signal out of a corporate action.
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
        timeout=timeout,
    )


def _extract_close(frame: pd.DataFrame, tickers: Sequence[str]) -> Dict[str, pd.Series]:
    """Pull one clean close series per ticker out of yfinance's wide frame.

    The frame's index is the union of every market's trading days, so a Paris
    listing carries NaN on Thanksgiving and a US listing carries NaN on Ascension.
    Dropping those per symbol is essential, not cosmetic: pandas' rolling windows
    treat an embedded NaN as missing, so a NaN-padded series yields NaN for every
    SMA and band that spans one.
    """
    out: Dict[str, pd.Series] = {}
    for ticker in tickers:
        try:
            if isinstance(frame.columns, pd.MultiIndex):
                if ticker not in frame.columns.get_level_values(0):
                    continue
                series = frame[ticker]["Close"]
            else:
                series = frame["Close"]
        except KeyError:
            continue

        series = pd.to_numeric(series, errors="coerce").dropna()
        if series.empty:
            continue
        series.index = pd.DatetimeIndex(series.index).tz_localize(None).normalize()
        out[ticker] = series[~series.index.duplicated(keep="last")].sort_index()
    return out


def fetch_closes(
    tickers: Sequence[str], period: str, cfg: UniverseConfig
) -> Tuple[Dict[str, pd.Series], List[Tuple[str, str]]]:
    """Fetch daily closes for `tickers`.

    Returns (closes by ticker, [(ticker, reason) for everything that produced no
    usable data]).
    """
    closes: Dict[str, pd.Series] = {}
    failed: List[Tuple[str, str]] = []
    batches = chunks(tickers, cfg.batch_size)

    for n, batch in enumerate(batches, start=1):
        frame = None
        last_error = "unknown"

        for attempt in range(cfg.max_retries):
            try:
                frame = _download(batch, period)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == cfg.max_retries - 1:
                    break
                # Exponential with jitter, so a rate limit is not met by 12
                # batches retrying in lockstep.
                delay = cfg.backoff_base_s * (2 ** attempt) + random.uniform(0, 1)
                log.warning(
                    "batch %d/%d attempt %d failed (%s); retrying in %.1fs",
                    n, len(batches), attempt + 1, last_error, delay,
                )
                time.sleep(delay)

        if frame is None:
            log.error("batch %d/%d gave up after %d attempts", n, len(batches), cfg.max_retries)
            failed.extend((t, f"batch download failed: {last_error}") for t in batch)
            continue

        got = _extract_close(frame, batch)
        closes.update(got)
        for ticker in batch:
            if ticker not in got:
                failed.append((ticker, "no price data returned"))

        log.info("batch %d/%d: %d/%d symbols ok", n, len(batches), len(got), len(batch))

    return closes, failed

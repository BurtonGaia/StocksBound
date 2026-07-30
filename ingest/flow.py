"""Tab 1: relative strength and breadth per (sector, geography) cell.

Relative strength is the equal-weight mean return of a cell's constituents minus
the equal-weight mean return of that entire geography, over a calendar horizon.

Relative, because an absolute number only tells you the market moved. Equal-weight,
because it needs no market-cap data -- which is what keeps this free -- and because
it stops five mega-caps from speaking for a whole sector.
"""
from __future__ import annotations

import logging
from statistics import fmean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from .sectors_map import GICS_SECTORS
from .signals import BEARISH, BULLISH, INSUFFICIENT_DATA, NEUTRAL
from .symbols import FRANCE, GERMANY, US

ALL = "ALL"

# Column order for Tab 1. ALL last, as a summary of the three real markets.
GEO_COLUMNS: Tuple[str, ...] = (US, FRANCE, GERMANY, ALL)

log = logging.getLogger(__name__)


def horizon_return(close: pd.Series, as_of: pd.Timestamp, days: int) -> Optional[float]:
    """Simple return over a calendar window ending at the series' last close.

    The window start is the last bar at or before `as_of - days`. Calendar-anchored
    rather than bar-counted so that US, Paris and Frankfurt windows cover the same
    stretch of wall-clock time despite different holiday calendars -- otherwise the
    cross-geography comparison Tab 1 exists for is quietly comparing unlike things.

    Returns None when history does not reach back far enough.
    """
    if close.empty:
        return None

    anchor = as_of - pd.Timedelta(days=days)
    past = close.loc[close.index <= anchor]
    if past.empty:
        return None

    start = float(past.iloc[-1])
    if start <= 0:
        return None
    return float(close.iloc[-1]) / start - 1.0


def compute_returns(
    closes: Dict[str, pd.Series], as_of: pd.Timestamp, horizons: Dict[str, int]
) -> Dict[str, Dict[str, Optional[float]]]:
    return {
        symbol: {label: horizon_return(series, as_of, days) for label, days in horizons.items()}
        for symbol, series in closes.items()
    }


def _mean_return(
    symbols: Iterable[str], returns: Dict[str, Dict[str, Optional[float]]], horizon: str
) -> Optional[float]:
    """Equal-weight mean, skipping symbols without enough history for this horizon."""
    values = [
        returns[s][horizon]
        for s in symbols
        if s in returns and returns[s].get(horizon) is not None
    ]
    return fmean(values) if values else None


def _breadth(symbols: Iterable[str], daily_signals: Dict[str, str]) -> Dict[str, int]:
    counts = {"bullish": 0, "bearish": 0, "neutral": 0, "insufficient": 0}
    key = {
        BULLISH: "bullish",
        BEARISH: "bearish",
        NEUTRAL: "neutral",
        INSUFFICIENT_DATA: "insufficient",
    }
    for symbol in symbols:
        signal = daily_signals.get(symbol)
        if signal in key:
            counts[key[signal]] += 1
        else:
            counts["insufficient"] += 1
    return counts


def build_flow(
    constituents: Sequence["object"],
    returns: Dict[str, Dict[str, Optional[float]]],
    daily_signals: Dict[str, str],
    horizons: Dict[str, int],
) -> Tuple[List[dict], List[dict]]:
    """Return (cells, baselines).

    Every one of the 11 x 4 cells is emitted, including the empty ones as n=0 with
    null strengths. A missing cell and a genuinely empty cell are different facts,
    and Tab 1 is supposed to show the difference rather than hide it.
    """
    # Constituents with an unmapped sector have no cell to live in. The run fails
    # on them anyway; excluding them here keeps the arithmetic honest meanwhile.
    members = [c for c in constituents if getattr(c, "sector", None) is not None]

    by_geography: Dict[str, List[str]] = {geo: [] for geo in GEO_COLUMNS}
    by_cell: Dict[Tuple[str, str], List[str]] = {}

    for c in members:
        for geo in (c.geography, ALL):
            by_geography.setdefault(geo, []).append(c.yahoo_symbol)
            by_cell.setdefault((c.sector, geo), []).append(c.yahoo_symbol)

    baselines = []
    for geo in GEO_COLUMNS:
        symbols = by_geography.get(geo, [])
        row = {"geography": geo, "n": len(symbols)}
        for horizon in horizons:
            row[f"ret_{horizon}"] = _round(_mean_return(symbols, returns, horizon))
        baselines.append(row)

    baseline_lookup = {b["geography"]: b for b in baselines}

    cells = []
    for sector in GICS_SECTORS:
        for geo in GEO_COLUMNS:
            symbols = by_cell.get((sector, geo), [])
            cell = {
                "sector": sector,
                "geography": geo,
                "n": len(symbols),
                "breadth": _breadth(symbols, daily_signals),
            }
            for horizon in horizons:
                sector_mean = _mean_return(symbols, returns, horizon)
                geo_mean = baseline_lookup[geo].get(f"ret_{horizon}")
                cell[f"rel_{horizon}"] = (
                    _round(sector_mean - geo_mean)
                    if sector_mean is not None and geo_mean is not None
                    else None
                )
            cells.append(cell)

    return cells, baselines


def _round(value: Optional[float], digits: int = 6) -> Optional[float]:
    return None if value is None else round(value, digits)

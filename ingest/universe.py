"""Index constituents, scraped from Wikipedia with a committed CSV fallback.

The scrape locates its table by *content* -- required column headers plus a
plausible row count -- rather than by position, so a new table appearing on the
page does not shift everything by one. If anything at all goes wrong, the index
falls back to its committed CSV and says so in meta.json. A Wikipedia layout
change degrades the data's freshness; it never breaks the pipeline.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
import requests

from .config import STATIC_DIR
from .sectors_map import canonical_sector, normalize_label
from .symbols import INDEX_GEOGRAPHY, YAHOO_SUFFIX, exchange_suffix, to_yahoo

log = logging.getLogger(__name__)

USER_AGENT = "sector-flow/0.1 (personal sector screener; https://github.com)"
REQUEST_TIMEOUT_S = 30

# Resolution order when the same symbol is claimed by two indices.
INDEX_PRIORITY = ("SP500", "CAC40", "DAX")


@dataclass(frozen=True)
class IndexSpec:
    name: str
    url: str
    min_rows: int
    max_rows: int
    # Candidates are tried in order, exact match before substring, so a specific
    # header ("Prime Standard Sector") is never shadowed by a generic one.
    ticker_cols: Sequence[str]
    name_cols: Sequence[str]
    sector_cols: Sequence[str]


INDEX_SPECS: Tuple[IndexSpec, ...] = (
    IndexSpec(
        name="SP500",
        url="https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        min_rows=450,
        max_rows=520,
        ticker_cols=("Symbol", "Ticker"),
        name_cols=("Security", "Company"),
        sector_cols=("GICS Sector", "Sector"),
    ),
    IndexSpec(
        name="CAC40",
        url="https://en.wikipedia.org/wiki/CAC_40",
        min_rows=35,
        max_rows=45,
        ticker_cols=("Ticker", "Symbol"),
        name_cols=("Company", "Security"),
        sector_cols=("Sector", "GICS Sector"),
    ),
    IndexSpec(
        name="DAX",
        url="https://en.wikipedia.org/wiki/DAX",
        min_rows=35,
        max_rows=45,
        ticker_cols=("Ticker", "Symbol"),
        name_cols=("Company", "Security"),
        sector_cols=("Prime Standard Sector", "Sector"),
    ),
)


@dataclass(frozen=True)
class Constituent:
    symbol: str          # display ticker, as published (BRK.B, AC.PA)
    yahoo_symbol: str    # what we actually fetch (BRK-B, AC.PA)
    name: str
    index: str
    geography: str
    sector_raw: str
    sector: Optional[str]  # canonical GICS, or None when unmapped


@dataclass
class UniverseResult:
    constituents: List[Constituent]
    sources: Dict[str, str] = field(default_factory=dict)          # index -> wikipedia|fallback_csv
    unmapped: List[Tuple[str, str]] = field(default_factory=list)  # (raw label, index)
    duplicates: List[Tuple[str, str, str]] = field(default_factory=list)  # symbol, kept, dropped


# --- column and table discovery ---------------------------------------------

def _pick_column(frame: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    """Find a column by fuzzy header match. Exact wins over substring, always."""
    headers = {normalize_label(str(c)): c for c in frame.columns}
    for cand in candidates:
        key = normalize_label(cand)
        if key in headers:
            return headers[key]
    for cand in candidates:
        key = normalize_label(cand)
        for norm, original in headers.items():
            if key in norm:
                return original
    return None


def _find_table(tables: Sequence[pd.DataFrame], spec: IndexSpec) -> pd.DataFrame:
    for frame in tables:
        if isinstance(frame.columns, pd.MultiIndex):
            continue
        if not spec.min_rows <= len(frame) <= spec.max_rows:
            continue
        if all(
            _pick_column(frame, cols) is not None
            for cols in (spec.ticker_cols, spec.name_cols, spec.sector_cols)
        ):
            return frame
    raise LookupError(
        f"{spec.name}: no table on {spec.url} had {spec.min_rows}-{spec.max_rows} rows "
        f"plus ticker/name/sector columns. Page layout has probably changed."
    )


def _scrape(spec: IndexSpec) -> List[Tuple[str, str, str]]:
    response = requests.get(
        spec.url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_S
    )
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    frame = _find_table(tables, spec)

    ticker_col = _pick_column(frame, spec.ticker_cols)
    name_col = _pick_column(frame, spec.name_cols)
    sector_col = _pick_column(frame, spec.sector_cols)

    rows = []
    for _, row in frame.iterrows():
        ticker = str(row[ticker_col]).strip()
        if not ticker or ticker.lower() == "nan":
            continue
        rows.append((ticker, str(row[name_col]).strip(), str(row[sector_col]).strip()))
    return rows


# --- fallback ----------------------------------------------------------------

def fallback_path(index: str) -> "object":
    return STATIC_DIR / f"fallback_{index.lower()}.csv"


def _load_fallback(index: str) -> List[Tuple[str, str, str]]:
    with open(fallback_path(index), newline="", encoding="utf-8") as fh:
        return [
            (r["symbol"].strip(), r["name"].strip(), r["sector_raw"].strip())
            for r in csv.DictReader(fh)
        ]


def write_fallback(index: str, rows: Sequence[Tuple[str, str, str]]) -> None:
    """Refresh a committed fallback from a good scrape. Called by the weekly job."""
    with open(fallback_path(index), "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["symbol", "name", "sector_raw"])
        writer.writerows(rows)


# --- assembly ----------------------------------------------------------------

def _suffix_matches_geography(ticker: str, geography: str) -> bool:
    """True when the ticker's venue agrees with its index's home market.

    Used to settle a symbol claimed by two indices. Airbus is in both the CAC 40
    and the DAX and trades as AIR.PA, so Paris has the better claim.
    """
    suffix = exchange_suffix(ticker, geography)
    return suffix == "" or suffix == YAHOO_SUFFIX[geography]


def _dedupe(constituents: Sequence[Constituent]) -> Tuple[List[Constituent], List[Tuple[str, str, str]]]:
    by_symbol: Dict[str, List[Constituent]] = {}
    for c in constituents:
        by_symbol.setdefault(c.yahoo_symbol, []).append(c)

    kept, dropped = [], []
    for symbol, claims in by_symbol.items():
        if len(claims) == 1:
            kept.append(claims[0])
            continue
        claims = sorted(
            claims,
            key=lambda c: (
                not _suffix_matches_geography(c.symbol, c.geography),
                INDEX_PRIORITY.index(c.index) if c.index in INDEX_PRIORITY else 99,
            ),
        )
        kept.append(claims[0])
        for loser in claims[1:]:
            dropped.append((symbol, claims[0].index, loser.index))
    return kept, dropped


def build_universe(specs: Sequence[IndexSpec] = INDEX_SPECS) -> UniverseResult:
    result = UniverseResult(constituents=[])
    raw_constituents: List[Constituent] = []

    for spec in specs:
        try:
            rows = _scrape(spec)
            source = "wikipedia"
        except Exception as exc:  # noqa: BLE001 - any failure must degrade, not abort
            log.warning("%s: scrape failed (%s); using committed fallback", spec.name, exc)
            rows = _load_fallback(spec.name)
            source = "fallback_csv"

        result.sources[spec.name] = source
        geography = INDEX_GEOGRAPHY[spec.name]

        for ticker, name, sector_raw in rows:
            sector = canonical_sector(sector_raw)
            if sector is None:
                result.unmapped.append((sector_raw, spec.name))
            raw_constituents.append(
                Constituent(
                    symbol=ticker.upper(),
                    yahoo_symbol=to_yahoo(ticker, geography),
                    name=name,
                    index=spec.name,
                    geography=geography,
                    sector_raw=sector_raw,
                    sector=sector,
                )
            )

    result.constituents, result.duplicates = _dedupe(raw_constituents)
    result.constituents.sort(key=lambda c: (c.geography, c.symbol))
    return result

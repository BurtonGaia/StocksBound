"""Constituent scraping, against inline HTML. No network."""
from __future__ import annotations

import io

import pandas as pd
import pytest

from ingest import universe as U
from ingest.symbols import FRANCE, GERMANY
from ingest.universe import Constituent, IndexSpec, _dedupe, _find_table, _pick_column

SPEC = IndexSpec(
    name="CAC40",
    url="http://example.invalid",
    min_rows=2,
    max_rows=50,
    ticker_cols=("Ticker", "Symbol"),
    name_cols=("Company", "Security"),
    sector_cols=("Sector", "GICS Sector"),
)

DAX_SPEC = IndexSpec(
    name="DAX",
    url="http://example.invalid",
    min_rows=2,
    max_rows=50,
    ticker_cols=("Ticker",),
    name_cols=("Company",),
    sector_cols=("Prime Standard Sector", "Sector"),
)


def frame(rows, columns) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


# --- column discovery --------------------------------------------------------

def test_pick_column_prefers_an_exact_match_over_a_substring():
    """Guards the DAX case: a generic 'Sector' candidate must not swallow
    'Prime Standard Sector' when a better match exists."""
    df = frame([], ["Ticker", "Prime Standard Sector", "Sector"])
    assert _pick_column(df, DAX_SPEC.sector_cols) == "Prime Standard Sector"
    assert _pick_column(df, ("Sector",)) == "Sector"


def test_pick_column_falls_back_to_substring():
    df = frame([], ["Ticker", "Prime Standard Sector"])
    assert _pick_column(df, ("Sector",)) == "Prime Standard Sector"


def test_pick_column_is_case_and_spacing_insensitive():
    df = frame([], ["  gics   SECTOR "])
    assert _pick_column(df, ("GICS Sector",)) is not None


def test_pick_column_returns_none_when_absent():
    assert _pick_column(frame([], ["A", "B"]), ("Sector",)) is None


# --- table discovery ---------------------------------------------------------

def test_find_table_ignores_decoys_and_picks_on_content():
    decoy_small = frame([[1, 2]], ["Ticker", "Sector"])
    decoy_wrong_cols = frame([[1, 2, 3]] * 5, ["Year", "Closing level", "Change"])
    real = frame([["AI.PA", "Air Liquide", "Basic Materials"]] * 5, ["Ticker", "Company", "Sector"])
    found = _find_table([decoy_small, decoy_wrong_cols, real], SPEC)
    assert list(found.columns) == ["Ticker", "Company", "Sector"]


def test_find_table_skips_multiindex_tables():
    """The S&P page carries a MultiIndex 'changes' table of a plausible size."""
    multi = pd.DataFrame(
        [["a", "b", "c"]] * 5,
        columns=pd.MultiIndex.from_tuples([("Added", "Ticker"), ("Added", "Company"), ("x", "Sector")]),
    )
    real = frame([["AI.PA", "Air Liquide", "Energy"]] * 5, ["Ticker", "Company", "Sector"])
    assert _find_table([multi, real], SPEC) is real


def test_find_table_raises_when_the_layout_has_changed():
    with pytest.raises(LookupError, match="layout"):
        _find_table([frame([[1]] * 5, ["Nope"])], SPEC)


# --- scrape wiring, with requests stubbed -----------------------------------

HTML = """
<table><tr><th>Ticker</th><th>Company</th><th>Sector</th></tr>
<tr><td>AI.PA</td><td>Air Liquide</td><td>Basic Materials</td></tr>
<tr><td>MT.AS</td><td>ArcelorMittal</td><td>Basic Materials</td></tr>
<tr><td>AC.PA</td><td>Accor</td><td>Consumer Services</td></tr>
</table>
"""


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_scrape_extracts_ticker_name_sector(monkeypatch):
    monkeypatch.setattr(U.requests, "get", lambda *a, **k: FakeResponse(HTML))
    rows = U._scrape(SPEC)
    assert rows == [
        ("AI.PA", "Air Liquide", "Basic Materials"),
        ("MT.AS", "ArcelorMittal", "Basic Materials"),
        ("AC.PA", "Accor", "Consumer Services"),
    ]


def test_build_universe_falls_back_to_csv_when_the_scrape_fails(monkeypatch):
    """A Wikipedia layout change must cost freshness, never the pipeline."""
    def explode(*a, **k):
        raise RuntimeError("layout changed")

    monkeypatch.setattr(U, "_scrape", explode)
    result = U.build_universe()
    assert set(result.sources.values()) == {"fallback_csv"}
    assert len(result.constituents) > 500
    assert not result.unmapped


def test_build_universe_maps_every_committed_fallback_sector(monkeypatch):
    """The committed CSVs must be fully covered by sector_map.csv."""
    monkeypatch.setattr(U, "_scrape", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    result = U.build_universe()
    assert result.unmapped == []
    assert all(c.sector is not None for c in result.constituents)


# --- dedupe ------------------------------------------------------------------

def make(symbol, index, geography, yahoo=None) -> Constituent:
    return Constituent(
        symbol=symbol,
        yahoo_symbol=yahoo or symbol,
        name=symbol,
        index=index,
        geography=geography,
        sector_raw="Industrials",
        sector="Industrials",
    )


def test_dedupe_awards_a_dual_listed_symbol_to_its_actual_venue():
    """Airbus is in both the CAC 40 and the DAX, and trades as AIR.PA. Paris has
    the better claim; without this the same company is counted twice and inflates
    both the sector mean and the ALL baseline."""
    claims = [make("AIR.PA", "DAX", GERMANY), make("AIR.PA", "CAC40", FRANCE)]
    kept, dropped = _dedupe(claims)
    assert len(kept) == 1
    assert kept[0].index == "CAC40"
    assert dropped == [("AIR.PA", "CAC40", "DAX")]


def test_dedupe_leaves_unique_symbols_alone():
    claims = [make("SAP.DE", "DAX", GERMANY), make("AI.PA", "CAC40", FRANCE)]
    kept, dropped = _dedupe(claims)
    assert len(kept) == 2
    assert dropped == []


def test_dedupe_keeps_a_foreign_listing_when_it_is_the_only_claim():
    """ArcelorMittal is CAC 40 but Amsterdam-listed. It stays in France."""
    kept, dropped = _dedupe([make("MT.AS", "CAC40", FRANCE)])
    assert len(kept) == 1
    assert kept[0].geography == FRANCE
    assert dropped == []

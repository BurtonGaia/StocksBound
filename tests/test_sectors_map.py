from __future__ import annotations

import pytest

from ingest.sectors_map import GICS_SECTORS, canonical_sector, load_sector_map, normalize_label


def test_there_are_exactly_eleven_gics_sectors():
    assert len(GICS_SECTORS) == 11
    assert len(set(GICS_SECTORS)) == 11


def test_every_gics_sector_maps_to_itself():
    for sector in GICS_SECTORS:
        assert canonical_sector(sector) == sector


def test_the_map_only_ever_targets_a_gics_sector():
    assert set(load_sector_map().values()) <= set(GICS_SECTORS)


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Yahoo's taxonomy
        ("Technology", "Information Technology"),
        ("Financial Services", "Financials"),
        ("Consumer Cyclical", "Consumer Discretionary"),
        ("Consumer Defensive", "Consumer Staples"),
        ("Basic Materials", "Materials"),
        ("Healthcare", "Health Care"),
        # ICB / European labels
        ("Oil & Gas", "Energy"),
        ("Chemicals", "Materials"),
        ("Industrial Goods & Services", "Industrials"),
        ("Automobiles & Parts", "Consumer Discretionary"),
        ("Food & Beverage", "Consumer Staples"),
        ("Pharmaceuticals & Biotechnology", "Health Care"),
        ("Banks", "Financials"),
        ("Insurance", "Financials"),
        ("Telecommunications", "Communication Services"),
        ("Software & Computer Services", "Information Technology"),
        ("Electricity", "Utilities"),
        ("Real Estate Investment Trusts", "Real Estate"),
    ],
)
def test_vendor_labels_fold_into_gics(raw, expected):
    assert canonical_sector(raw) == expected


@pytest.mark.parametrize(
    "variant",
    ["health care", "HEALTH CARE", "  Health   Care  ", "Health-Care"],
)
def test_cosmetic_variation_is_folded(variant):
    assert canonical_sector(variant) == "Health Care"


@pytest.mark.parametrize("variant", ["Oil & Gas", "Oil and Gas", "OIL  &  GAS"])
def test_ampersand_and_the_word_and_are_equivalent(variant):
    assert canonical_sector(variant) == "Energy"


@pytest.mark.parametrize("raw", [None, "", "   ", "Blockchain", "Prime Standard: Widgets"])
def test_unknown_labels_return_none_rather_than_a_bucket(raw):
    """None is the caller's cue to record it in meta.json and fail the run. There
    is deliberately no 'Other' sector to fall into."""
    assert canonical_sector(raw) is None


def test_normalize_label():
    assert normalize_label("  Consumer   Discretionary ") == "consumer discretionary"
    assert normalize_label("Oil & Gas") == "oil and gas"
    assert normalize_label("Personal Care, Drug & Grocery Stores") == (
        "personal care drug and grocery stores"
    )

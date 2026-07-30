from __future__ import annotations

import pytest

from ingest.symbols import (
    FRANCE,
    GERMANY,
    US,
    exchange_suffix,
    normalize_symbol,
    to_yahoo,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("BRK.B", "BRK-B"),
        ("BF.B", "BF-B"),
        ("AAPL", "AAPL"),
        ("aapl", "AAPL"),
        (" MSFT ", "MSFT"),
        ("VOW3", "VOW3"),
        ("1COV", "1COV"),
    ],
)
def test_normalize_symbol(raw, expected):
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize(
    "raw,geo,expected",
    [
        ("AAPL", US, "AAPL"),
        ("BRK.B", US, "BRK-B"),
        ("AI", FRANCE, "AI.PA"),
        ("MC", FRANCE, "MC.PA"),
        ("SAP", GERMANY, "SAP.DE"),
        ("VOW3", GERMANY, "VOW3.DE"),
        ("1COV", GERMANY, "1COV.DE"),
    ],
)
def test_to_yahoo(raw, geo, expected):
    assert to_yahoo(raw, geo) == expected


@pytest.mark.parametrize(
    "raw,geo,expected",
    [
        ("AI.PA", FRANCE, "AI.PA"),
        ("SAP.DE", GERMANY, "SAP.DE"),
        ("sap.de", GERMANY, "SAP.DE"),
    ],
)
def test_to_yahoo_is_idempotent_on_already_suffixed_symbols(raw, geo, expected):
    """Sources publish bare tickers and Yahoo symbols interchangeably. Appending
    blindly would produce AI-PA.PA and drop the constituent silently."""
    assert to_yahoo(raw, geo) == expected
    assert to_yahoo(to_yahoo(raw, geo), geo) == expected


def test_us_symbols_get_no_suffix():
    assert to_yahoo("JPM", US) == "JPM"


@pytest.mark.parametrize(
    "raw,geo,expected",
    [
        # ArcelorMittal is a CAC 40 member listed in Amsterdam.
        ("MT.AS", FRANCE, "MT.AS"),
        # Airbus is a DAX member listed in Paris.
        ("AIR.PA", GERMANY, "AIR.PA"),
        ("ABI.BR", FRANCE, "ABI.BR"),
        ("NESN.SW", GERMANY, "NESN.SW"),
    ],
)
def test_an_explicit_exchange_suffix_beats_the_index_default(raw, geo, expected):
    """Index membership does not imply listing venue. Overriding a real suffix
    builds a symbol like MT-AS.PA, which fetches nothing and drops the
    constituent silently."""
    assert to_yahoo(raw, geo) == expected


def test_us_share_classes_are_never_read_as_exchange_suffixes():
    """`.L` is London, but a US ticker's dot is always a share class. The suffix
    list is consulted for non-US geographies only, so these cannot collide."""
    assert to_yahoo("BRK.B", US) == "BRK-B"
    assert to_yahoo("BF.B", US) == "BF-B"


@pytest.mark.parametrize(
    "raw,geo,expected",
    [("MT.AS", FRANCE, ".AS"), ("AI.PA", FRANCE, ".PA"), ("AI", FRANCE, ""), ("BRK.B", US, "")],
)
def test_exchange_suffix(raw, geo, expected):
    assert exchange_suffix(raw, geo) == expected


def test_unknown_geography_raises():
    with pytest.raises(ValueError):
        to_yahoo("AAPL", "Belgium")

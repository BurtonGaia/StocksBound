"""Exchange ticker -> Yahoo Finance symbol.

One function, one place, tested. Getting this wrong does not raise -- it silently
drops a constituent from the universe, which is exactly the kind of failure that
never gets noticed.
"""
from __future__ import annotations

import re

US = "US"
FRANCE = "France"
GERMANY = "Germany"

GEOGRAPHIES = (US, FRANCE, GERMANY)

YAHOO_SUFFIX = {US: "", FRANCE: ".PA", GERMANY: ".DE"}

INDEX_GEOGRAPHY = {"SP500": US, "CAC40": FRANCE, "DAX": GERMANY}

# Yahoo exchange suffixes that may legitimately appear on a European constituent.
#
# Index membership does not imply listing venue: ArcelorMittal sits in the CAC 40
# but trades in Amsterdam as MT.AS, and Airbus sits in the DAX but trades in Paris
# as AIR.PA. When a source hands over an explicit suffix it is telling us the real
# venue, and that beats the index default -- overriding it would build symbols like
# MT-AS.PA that fetch nothing and drop the constituent without a word.
#
# Deliberately consulted only for non-US geographies. US sources publish bare
# tickers or dotted share classes (BRK.B, BF.B), never exchange suffixes, so this
# list can never be mistaken for a share-class marker.
_EXCHANGE_SUFFIXES = (
    ".PA",  # Paris
    ".DE",  # XETRA
    ".AS",  # Amsterdam
    ".BR",  # Brussels
    ".MC",  # Madrid
    ".MI",  # Milan
    ".SW",  # Zurich
    ".VI",  # Vienna
    ".LS",  # Lisbon
    ".IR",  # Dublin
    ".CO",  # Copenhagen
    ".ST",  # Stockholm
    ".HE",  # Helsinki
    ".OL",  # Oslo
    ".L",   # London
)

_WHITESPACE = re.compile(r"\s+")


def normalize_symbol(raw: str) -> str:
    """Punctuation normalisation only, no suffix logic.

    Yahoo writes share classes with a hyphen where exchanges use a dot:
    BRK.B -> BRK-B, BF.B -> BF-B.
    """
    s = _WHITESPACE.sub("", str(raw)).upper()
    return s.replace(".", "-")


def exchange_suffix(raw: str, geography: str) -> str:
    """The explicit Yahoo exchange suffix on `raw`, or "" if it carries none."""
    if geography == US:
        return ""
    s = _WHITESPACE.sub("", str(raw)).upper()
    for suffix in _EXCHANGE_SUFFIXES:
        if s.endswith(suffix) and len(s) > len(suffix):
            return suffix
    return ""


def to_yahoo(raw: str, geography: str) -> str:
    """Full Yahoo symbol for a ticker in a given geography.

    An explicit exchange suffix is preserved; a bare ticker gets the geography's
    default. So for a CAC 40 scrape, "AI" and "AI.PA" both give "AI.PA", while
    "MT.AS" stays "MT.AS" rather than becoming "MT-AS.PA".

    Idempotent by construction, because the source publishes bare tickers and
    Yahoo symbols interchangeably and we cannot tell which we are being handed.
    """
    if geography not in YAHOO_SUFFIX:
        raise ValueError(f"unknown geography {geography!r}, expected one of {GEOGRAPHIES}")

    s = _WHITESPACE.sub("", str(raw)).upper()
    suffix = exchange_suffix(s, geography)
    if suffix:
        return normalize_symbol(s[: -len(suffix)]) + suffix

    return normalize_symbol(s) + YAHOO_SUFFIX[geography]

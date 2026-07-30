"""Vendor sector labels -> the 11 GICS sectors.

US constituents arrive as GICS, European ones as ICB or a vendor's own wording.
Cross-geography sector comparison is the entire point of Tab 1, so an unmapped
label is a hard failure, never a quiet fallback into "Other".
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from .config import STATIC_DIR

GICS_SECTORS = (
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
)

SECTOR_MAP_PATH = STATIC_DIR / "sector_map.csv"

_PUNCT = re.compile(r"[.,/()\-']")
_WHITESPACE = re.compile(r"\s+")


def normalize_label(raw: str) -> str:
    """Fold the variation that is purely cosmetic, so the table stays short."""
    s = str(raw).strip().lower()
    s = s.replace("&", " and ")
    s = _PUNCT.sub(" ", s)
    return _WHITESPACE.sub(" ", s).strip()


@lru_cache(maxsize=1)
def load_sector_map(path: Path = SECTOR_MAP_PATH) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        # The file carries comments explaining the provenance of each block; the
        # csv module has no notion of those, so strip them first.
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]

    for row in csv.DictReader(lines):
        key = normalize_label(row["raw"])
        target = row["gics"].strip()
        if target not in GICS_SECTORS:
            raise ValueError(f"sector_map.csv maps {row['raw']!r} to non-GICS {target!r}")
        if key in mapping and mapping[key] != target:
            raise ValueError(
                f"sector_map.csv maps {key!r} to both {mapping[key]!r} and {target!r}"
            )
        mapping[key] = target
    return mapping


def canonical_sector(raw: Optional[str]) -> Optional[str]:
    """The GICS sector for a vendor label, or None if it is not in the table.

    None is the caller's signal to record the label in meta.json and fail the run.
    """
    if raw is None:
        return None
    key = normalize_label(raw)
    if not key:
        return None
    return load_sector_map().get(key)

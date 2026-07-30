"""JSON writers for the three artifacts.

latest.json is written one record per line. It is committed every day, so a
readable git diff is worth a few bytes -- a single row changing shows up as a
single changed line instead of a 600-line reflow. sectors.json and meta.json are
small enough to pretty-print outright.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Sequence

log = logging.getLogger(__name__)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    log.info("wrote %s (%.1f KB)", path.name, len(text) / 1024)


def write_latest(path: Path, header: dict, rows: Sequence[dict]) -> None:
    parts = [
        "{",
        *[f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in header.items()],
        '  "rows": [',
    ]
    encoded = [
        "    " + json.dumps(row, separators=(",", ":"), allow_nan=False) for row in rows
    ]
    parts.append(",\n".join(encoded))
    parts.append("  ]")
    parts.append("}")
    _write(path, "\n".join(parts))


def write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, indent=2, allow_nan=False))

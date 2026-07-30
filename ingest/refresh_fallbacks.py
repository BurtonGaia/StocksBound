"""Refresh the committed constituent CSVs from a live scrape.

Run weekly by its own workflow, separately from the daily price ingest. A
successful scrape overwrites the fallback; a failed one leaves the last good copy
in place, which is the entire point of the fallback existing.

    python -m ingest.refresh_fallbacks
"""
from __future__ import annotations

import logging
import sys

from .universe import INDEX_SPECS, _scrape, write_fallback

log = logging.getLogger("refresh_fallbacks")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    failures = 0

    for spec in INDEX_SPECS:
        try:
            rows = _scrape(spec)
        except Exception as exc:  # noqa: BLE001
            log.error("%s: scrape failed, keeping existing fallback (%s)", spec.name, exc)
            failures += 1
            continue

        if not spec.min_rows <= len(rows) <= spec.max_rows:
            log.error(
                "%s: scrape returned %d rows, outside %d-%d; refusing to overwrite "
                "the fallback with something that looks wrong",
                spec.name, len(rows), spec.min_rows, spec.max_rows,
            )
            failures += 1
            continue

        write_fallback(spec.name, rows)
        log.info("%s: wrote %d constituents to fallback", spec.name, len(rows))

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

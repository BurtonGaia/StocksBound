"""Daily ingest entrypoint.

    python -m ingest.run [--cache PATH] [--out DIR] [--limit N]

Order of operations is deliberate: artifacts are written and committed *before* the
run asserts on unmapped sectors, so a taxonomy change turns the build red without
throwing away a perfectly good day of data.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List

import pandas as pd

from . import emit, history
from .config import DATA_DIR, REPO_ROOT, SCHEMA_VERSION, get_config
from .fetch import fetch_closes
from .flow import build_flow, compute_returns
from .resample import to_weekly
from .signals import changed, classify, latest_state
from .universe import build_universe

log = logging.getLogger("ingest")

DEFAULT_CACHE = REPO_ROOT / ".cache" / "daily_closes.csv.gz"
INCREMENTAL_PERIOD = "1mo"  # generous buffer over a weekend plus a holiday


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the sector-flow data artifacts")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path, default=DATA_DIR)
    parser.add_argument(
        "--limit", type=int, default=None, help="only process the first N constituents"
    )
    parser.add_argument(
        "--full", action="store_true", help="ignore the cache and backfill everything"
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = parse_args(argv)
    cfg = get_config()
    started = time.monotonic()

    # --- universe ------------------------------------------------------------
    universe = build_universe()
    constituents = universe.constituents
    if args.limit:
        constituents = constituents[: args.limit]
    symbols = [c.yahoo_symbol for c in constituents]
    log.info("universe: %d constituents from %s", len(symbols), universe.sources)

    # --- prices --------------------------------------------------------------
    cached = pd.DataFrame() if args.full else history.load(args.cache)
    backfill, update = history.split_by_coverage(cached, symbols, cfg.signal.min_bars)
    log.info("prices: %d need backfill, %d need a top-up", len(backfill), len(update))

    fetched: Dict[str, pd.Series] = {}
    failures: List[tuple] = []

    if backfill:
        got, failed = fetch_closes(backfill, f"{cfg.universe.history_years}y", cfg.universe)
        fetched.update(got)
        failures.extend(failed)
    if update:
        got, failed = fetch_closes(update, INCREMENTAL_PERIOD, cfg.universe)
        fetched.update(got)
        failures.extend(failed)

    merged = history.merge(cached, history.to_frame(fetched))
    if merged.empty:
        log.error("no price data at all; refusing to write empty artifacts")
        return 2

    merged = history.trim(merged, cfg.universe.history_years, keep_symbols=symbols)
    history.save(args.cache, merged)

    as_of = merged.index.max()
    log.info("as_of %s (%d bars x %d symbols)", as_of.date(), len(merged), merged.shape[1])

    # --- classify ------------------------------------------------------------
    closes: Dict[str, pd.Series] = {}
    rows: List[dict] = []
    daily_signals: Dict[str, str] = {}

    for c in constituents:
        if c.yahoo_symbol not in merged.columns:
            continue
        # Per-symbol dropna is mandatory: the merged frame's index is the union of
        # three markets' trading days, and an embedded NaN makes every rolling
        # window spanning it return NaN.
        daily_close = merged[c.yahoo_symbol].dropna()
        if daily_close.empty:
            failures.append((c.yahoo_symbol, "no usable closes after merge"))
            continue
        closes[c.yahoo_symbol] = daily_close

        daily = latest_state(classify(daily_close, cfg.signal))
        weekly = latest_state(classify(to_weekly(daily_close), cfg.signal))
        for block in (daily, weekly):
            block["changed"] = changed(block["signal"], block["prev_signal"])

        daily_signals[c.yahoo_symbol] = daily["signal"]
        rows.append(
            {
                "symbol": c.symbol,
                "yahoo_symbol": c.yahoo_symbol,
                "name": c.name,
                "index": c.index,
                "geography": c.geography,
                "sector": c.sector,
                "daily": daily,
                "weekly": weekly,
            }
        )

    log.info("classified %d symbols, %d failures", len(rows), len(failures))

    # --- flow ----------------------------------------------------------------
    returns = compute_returns(closes, as_of, cfg.horizons)
    cells, baselines = build_flow(constituents, returns, daily_signals, cfg.horizons)

    # --- emit ----------------------------------------------------------------
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    as_of_date = as_of.date().isoformat()
    out = args.out

    emit.write_latest(
        out / "latest.json",
        {"schema_version": SCHEMA_VERSION, "as_of": as_of_date, "generated_at": generated_at},
        rows,
    )
    emit.write_json(
        out / "sectors.json",
        {
            "schema_version": SCHEMA_VERSION,
            "as_of": as_of_date,
            "generated_at": generated_at,
            "horizons": list(cfg.horizons.keys()),
            "baselines": baselines,
            "cells": cells,
        },
    )

    unmapped = sorted({(raw, index) for raw, index in universe.unmapped})
    emit.write_json(
        out / "meta.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "as_of": as_of_date,
            "run": {
                "symbols_requested": len(symbols),
                "symbols_ok": len(rows),
                "symbols_failed": len(failures),
                "duration_s": round(time.monotonic() - started, 1),
                "failed": [{"symbol": s, "reason": r} for s, r in sorted(set(failures))],
            },
            "universe": {
                index: {"source": source, "count": sum(1 for c in constituents if c.index == index)}
                for index, source in universe.sources.items()
            },
            "duplicates": [
                {"symbol": sym, "kept": kept, "dropped": dropped}
                for sym, kept, dropped in universe.duplicates
            ],
            "unmapped_sectors": [{"raw": raw, "index": index} for raw, index in unmapped],
            "params": cfg.params_dict(),
        },
    )

    # --- assert, after the artifacts are safely on disk ----------------------
    if unmapped:
        log.error(
            "%d unmapped sector label(s); add them to ingest/static/sector_map.csv: %s",
            len(unmapped), unmapped,
        )
        return 1

    log.info("done in %.1fs", time.monotonic() - started)
    return 0


if __name__ == "__main__":
    sys.exit(main())

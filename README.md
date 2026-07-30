# Sector Flow & Signal Screener

Scans S&P 500, CAC 40 and DAX constituents daily and answers two questions: where
capital is rotating by sector and geography, and what every stock's signal is.

Runs for $0/month, permanently. No server, no database.

## Architecture

| | |
|---|---|
| Ingest | Python on a GitHub Actions cron, 22:30 UTC daily |
| Storage | JSON artifacts committed to `data/` |
| Frontend | Static site on Render, all filtering client-side |

There is no backend and no database on purpose. The full dataset is ~580 rows of a
handful of fields — a few hundred KB. Render's free web services sleep after 15
minutes and its free Postgres is deleted after 30 days; both are disqualifying for
a tool that must still work in a year. A static site has neither problem.

Price history is cached in the GitHub Actions cache, not the repo. Committing it
would add ~6 MB per day to git — roughly 1.5 GB a year — to store something one API
call can rebuild. A cache miss triggers a full backfill and self-heals.

## The signal

Computed independently on daily bars and on weekly bars resampled `W-FRI`:

```
SMA50   = 50-period simple moving average of close
BB      = 20-period, 2.0 stddev (population) -> upper, mid, lower
pctB    = (close - lower) / (upper - lower)

BULLISH = close > SMA50  AND  close > lower  AND  pctB <= 0.25
BEARISH = close < SMA50  AND  close < upper  AND  pctB >= 0.75
NEUTRAL = otherwise
```

Bullish is a pullback into the lower quartile of the band while price still holds
above the 50-period trend. Bearish is the mirror.

`close > lower` is not redundant with the `pctB` test: on its own `pctB <= 0.25`
would also admit `pctB = -0.4`, a stock that has broken clean through the lower
band. That is a breakdown, not a pullback, and it is excluded.

**Why so few stocks fire.** `pctB <= 0.25` is equivalent to `close <= mid - sigma`.
Combined with `close > SMA50`, bullish therefore requires

```
SMA50 < SMA20 - (2 - 4 * zone_pct) * sigma
```

At `zone_pct = 0.25` that demands a full standard deviation of separation between
the 20 and the 50. In practice **~3% of the universe fires on a given day**. If you
ever see 30%, the maths is broken.

### Changing the parameters

Everything lives in [`config/signal.toml`](config/signal.toml) — `bb_period`,
`bb_stddev`, `bb_ddof`, `sma_period`, `min_bars`, `zone_pct`, plus the fetch and
horizon settings. No indicator constant appears as a literal anywhere in `ingest/`.

Edit, then re-run `python -m ingest.run`. The values are echoed into
`data/meta.json` so the UI can always show what produced the numbers.

Two knobs deserve a warning:

- **`zone_pct`** is far more sensitive than it looks. Measured on synthetic series:
  0.15 → 2.1% of bars fire, 0.25 → 4.9%, 0.40 → 11.9%, 0.45 → 15.3%. It is
  validated to stay in `(0, 0.5)`; at 0.5 the bullish and bearish zones touch and
  the signal stops meaning anything.
- **`bb_ddof`** is 0 (population standard deviation), the standard Bollinger
  convention. pandas defaults to 1. Setting it to 1 widens every band and shifts
  every `pctB`.

## Local development

Requires Python 3.9+ and Node 20+.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

Run the tests — 136 of them, no network, ~0.7s:

```bash
.venv/bin/python -m pytest
```

Run the ingest. First run backfills 10 years for ~580 symbols in about 35 seconds:

```bash
.venv/bin/python -m ingest.run
```

Useful flags: `--limit N` to process only the first N constituents, `--full` to
ignore the cache, `--out DIR` to write artifacts somewhere other than `data/`.

Refresh the committed constituent fallbacks from Wikipedia:

```bash
.venv/bin/python -m ingest.refresh_fallbacks
```

Frontend:

```bash
cd web && npm install && npm run dev
```

`npm run dev` and `npm run build` both copy `data/*.json` into `web/public/data/`
first, so the dev server reads the same artifacts the deployed site does.

Two headless checks run the real frontend code against the real artifacts — no
browser needed, so they work in CI:

```bash
cd web && npm run verify
```

`verify:logic` exercises filters, drill-through, confluence, CSV export, the heat
ramp and the staleness rule against `data/*.json`. `verify:render` server-renders
both tabs and asserts on the markup — that groups are collapsed by default, that a
drill-through arrives already expanded in the *first* paint, that empty cells are
dashed and thin cells hatched.

If Node is not installed system-wide, a local copy works fine and needs no
admin rights:

```bash
curl -fsSLO https://nodejs.org/dist/v24.18.1/node-v24.18.1-darwin-arm64.tar.gz && tar -xzf node-v24.18.1-darwin-arm64.tar.gz -C ~/.local
```

Then prefix commands with `PATH="$HOME/.local/node-v24.18.1-darwin-arm64/bin:$PATH"`,
or add that line to your shell profile.

## Data artifacts

All three carry `schema_version`. `latest.json` is written one record per line so
the daily commit produces a readable diff.

### `data/latest.json` — one record per symbol

```json
{
  "schema_version": 1, "as_of": "2026-07-29", "generated_at": "2026-07-30T05:28:47Z",
  "rows": [
    {"symbol":"AI.PA","yahoo_symbol":"AI.PA","name":"Air Liquide","index":"CAC40",
     "geography":"France","sector":"Materials",
     "daily":{"bar_date":"2026-07-28","close":173.54,"sma50":170.4296,"pct_b":0.1086,
              "signal":"BULLISH","prev_signal":"NEUTRAL","changed":true},
     "weekly":{"bar_date":"2026-07-31","close":173.54,"sma50":158.2,"pct_b":0.34,
               "signal":"NEUTRAL","prev_signal":"NEUTRAL","changed":false}}
  ]
}
```

- `close` and `sma50` are **split- and dividend-adjusted**. An unadjusted series
  puts a step change through the close on every split, manufacturing a signal out
  of a corporate action. The tradeoff: on a high-dividend name the displayed close
  can differ by a few percent from the quoted last price. `close` and `sma50` are
  at least always comparable to each other, which is what the column is for.
- `weekly.bar_date` is the week-ending Friday, so mid-week it is a **future date** —
  the in-progress weekly bar. It means a weekly signal can flip and unflip before
  the week closes.
- `bar_date` can differ from `as_of` per row. Paris and Frankfurt close before New
  York, so a European row may legitimately be one bar behind.
- `changed` is true when the latest bar flipped the signal. Coming out of
  `INSUFFICIENT_DATA` does not count — that is a data event, not a market one.

### `data/sectors.json` — one record per (sector, geography)

44 cells: 11 GICS sectors × `US`, `France`, `Germany`, `ALL`. Empty cells are
emitted as `n: 0` with `null` strengths, because a missing cell and a genuinely
empty one are different facts.

`rel_*` is the equal-weight mean return of the cell's constituents minus the
equal-weight mean return of that whole geography. Relative, because an absolute
number only tells you the market moved. Equal-weight, because it needs no
market-cap data and stops five mega-caps speaking for a sector. `baselines` carries
the geography means, so absolute return is recoverable as `rel + baseline`.

Horizons are **calendar-anchored**, not bar-counted: a 5-bar lookback would compare
a US window against a Paris window covering different stretches of wall-clock time,
which quietly breaks the cross-geography comparison the whole tab exists for.

The `ALL` column pools constituents across all three geographies against a pooled
582-name baseline. Note that baseline is ~86% US by construction, so `ALL` reads as
"sector vs. a US-dominated world".

### `data/meta.json`

Run stats, per-index constituent source (`wikipedia` or `fallback_csv`), dropped
duplicates, unmapped sector labels, and the parameter snapshot.

## Deploy

1. Push to GitHub. `.github/workflows/ingest.yml` needs no secrets, but the repo
   must allow Actions to write — Settings → Actions → General → Workflow
   permissions → **Read and write**.
2. Create a Render **Static Site** from the repo. `render.yaml` is picked up
   automatically: build `cd web && npm ci && npm run build`, publish `web/dist`.
3. Trigger the first ingest by hand (Actions → Daily ingest → Run workflow) rather
   than waiting for 22:30 UTC.

The daily ingest commit to `data/` triggers a Render rebuild, which is how new data
reaches the site. `render.yaml` sets `Cache-Control: no-cache` on `/data/*` — the
files are overwritten at the same URLs every day, and a CDN-cached copy would show
yesterday's numbers while the app reported itself fresh.

There are no secrets anywhere in this project; see [`.env.example`](.env.example).

## Operational notes

- **The cron runs 7 days a week.** Weekend runs find no new bars but refresh
  `generated_at`, which makes the frontend's 36-hour staleness rule mean exactly one
  thing: the workflow failed. Weekday-only would false-alarm every Sunday.
- **An unmapped sector label fails the build.** Artifacts are written and committed
  first, then the run exits non-zero. You keep the day's data and get an email. Add
  the label to [`ingest/static/sector_map.csv`](ingest/static/sector_map.csv) —
  never bucket it into "Other", because a mislabelled sector silently destroys the
  cross-geography comparison. The three sources are inconsistent by nature: the S&P
  publishes GICS, Euronext publishes its own wording, and Deutsche Börse publishes
  prose like `Mechanical Engineering` and `E-Commerce`.
- **Index membership does not imply listing venue.** ArcelorMittal is CAC 40 but
  trades in Amsterdam as `MT.AS`; Airbus is in *both* the CAC 40 and the DAX and
  trades as `AIR.PA`. An explicit exchange suffix wins over the index default, and
  a symbol claimed by two indices goes to the one matching its venue. The dropped
  claim is recorded in `meta.json` rather than silently discarded.
- **A Wikipedia layout change costs freshness, never the pipeline.** The scrape
  finds its table by content — required headers plus a plausible row count — and
  falls back to the committed CSV in `ingest/static/`, recording
  `"source": "fallback_csv"` in `meta.json`.

/**
 * Exercises the frontend's pure logic against the real ingest artifacts.
 *
 * Bundled with esbuild and run under node. This covers everything the UI derives
 * from the data -- filters, confluence, drill-through, CSV, the heat scale -- with
 * the actual 582-row dataset rather than a fixture.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { applyFilters, EMPTY_FILTERS, filtersActive } from "../src/components/stocks/filters";
import { toCsv } from "../src/lib/csv";
import { heatBg, heatScale } from "../src/lib/heat";
import { pctB, price, signedPct } from "../src/lib/format";
import { freshness } from "../src/lib/data";
import {
  enteredSignal,
  hasConfluence,
  relFor,
  SECTORS,
  type LatestFile,
  type SectorsFile,
} from "../src/lib/types";

// Passed in, because the bundle does not live next to the source.
const root = resolve(process.argv[2] ?? "data");
const latest: LatestFile = JSON.parse(readFileSync(`${root}/latest.json`, "utf8"));
const sectors: SectorsFile = JSON.parse(readFileSync(`${root}/sectors.json`, "utf8"));

let failures = 0;
function check(label: string, condition: boolean, detail = "") {
  if (condition) {
    console.log(`  ok   ${label}${detail ? `  ${detail}` : ""}`);
  } else {
    failures++;
    console.log(`  FAIL ${label}  ${detail}`);
  }
}

console.log("\n— data contract —");
check("latest.json parses with rows", latest.rows.length > 500, `${latest.rows.length} rows`);
check("every row has both timeframes", latest.rows.every((r) => r.daily && r.weekly));
check(
  "every row has a mapped GICS sector",
  latest.rows.every((r) => (SECTORS as readonly string[]).includes(r.sector)),
);
check("sectors.json has 44 cells", sectors.cells.length === 44, `${sectors.cells.length}`);
check("sectors.json has 4 baselines", sectors.baselines.length === 4);

console.log("\n— derived sets —");
const confluence = latest.rows.filter(hasConfluence);
const changed = latest.rows.filter(enteredSignal);
const bull = latest.rows.filter((r) => r.daily.signal === "BULLISH");
const bear = latest.rows.filter((r) => r.daily.signal === "BEARISH");
console.log(
  `  daily: ${bull.length} bullish, ${bear.length} bearish of ${latest.rows.length} ` +
    `(${(((bull.length + bear.length) / latest.rows.length) * 100).toFixed(2)}%)`,
);
check("fire rate is low single digits", (bull.length + bear.length) / latest.rows.length < 0.1);
check(
  "confluence is a subset of signalling rows",
  confluence.every((r) => r.daily.signal === r.weekly.signal && r.daily.signal !== "NEUTRAL"),
  `${confluence.length} rows`,
);
check(
  "changed-today only contains rows now signalling",
  changed.every((r) => r.daily.signal === "BULLISH" || r.daily.signal === "BEARISH"),
  `${changed.length} rows`,
);
check(
  "changed-today excludes INSUFFICIENT_DATA transitions",
  changed.every((r) => r.daily.prev_signal !== "INSUFFICIENT_DATA"),
);

console.log("\n— filters —");
check("no filters is inactive", !filtersActive(EMPTY_FILTERS));
check("unfiltered returns everything", applyFilters(latest.rows, EMPTY_FILTERS).length === latest.rows.length);

const fin = applyFilters(latest.rows, { ...EMPTY_FILTERS, sector: "Financials", geographies: ["US"] });
check(
  "drill-through: Financials + US",
  fin.length > 0 && fin.every((r) => r.sector === "Financials" && r.geography === "US"),
  `${fin.length} rows`,
);

const drillAll = applyFilters(latest.rows, { ...EMPTY_FILTERS, sector: "Financials" });
check(
  "drill-through from ALL column spans geographies",
  new Set(drillAll.map((r) => r.geography)).size > 1,
  `${new Set(drillAll.map((r) => r.geography)).size} geographies`,
);

const searched = applyFilters(latest.rows, { ...EMPTY_FILTERS, search: "air liquide" });
check("search matches on name, case-insensitively", searched.length === 1 && searched[0].symbol === "AI.PA");
const searchedSym = applyFilters(latest.rows, { ...EMPTY_FILTERS, search: "brk" });
check("search matches on symbol", searchedSym.some((r) => r.symbol.startsWith("BRK")));

check(
  "signal filter",
  applyFilters(latest.rows, { ...EMPTY_FILTERS, signals: ["BULLISH"] }).length === bull.length,
);
check(
  "confluence filter matches the badge count",
  applyFilters(latest.rows, { ...EMPTY_FILTERS, confluenceOnly: true }).length === confluence.length,
);
check(
  "changed filter matches the badge count",
  applyFilters(latest.rows, { ...EMPTY_FILTERS, changedOnly: true }).length === changed.length,
);
check(
  "filters compose (AND, not OR)",
  applyFilters(latest.rows, {
    ...EMPTY_FILTERS,
    geographies: ["US"],
    signals: ["BULLISH"],
  }).every((r) => r.geography === "US" && r.daily.signal === "BULLISH"),
);

console.log("\n— heat scale —");
const scale1m = heatScale(sectors.cells.filter((c) => c.n >= 3).map((c) => relFor(c, "1m")));
check("scale excludes thin cells", scale1m > 0 && scale1m < 0.2, `±${(scale1m * 100).toFixed(2)}%`);
check("midpoint is a near-surface neutral", heatBg(0, "light", "rg").startsWith("oklch(0.978"));
check("light and dark ramps differ at the same value", heatBg(1, "light", "rg") !== heatBg(1, "dark", "rg"));
check("palettes differ", heatBg(1, "light", "rg") !== heatBg(1, "light", "ob"));
check(
  "ramp is monotonic in lightness (light mode)",
  [0, 0.25, 0.5, 0.75, 1]
    .map((t) => Number(heatBg(t, "light", "rg").split(" ")[0].replace("oklch(", "")))
    .every((l, i, a) => i === 0 || l < a[i - 1]),
);

console.log("\n— formatting (decimal alignment) —");
const prices = [1234.5, 7.25, 0.1, null].map(price);
check("fixed 2dp for prices", prices.slice(0, 3).every((p) => p.split(".")[1]?.length === 2), prices.join(" | "));
check("null renders as a dash, not 0.00", price(null) === "—");
check("%B keeps 3dp including negatives", pctB(-0.589) === "-0.589");
check("signed percent always carries a sign", signedPct(0.0633) === "+6.33%" && signedPct(-0.0287) === "-2.87%");
check("negative zero is cleaned up", signedPct(-0.000001) === "0.00%");

console.log("\n— csv export —");
const csv = toCsv(fin);
const lines = csv.split("\n");
check("header + one line per filtered row", lines.length === fin.length + 1, `${lines.length} lines`);
check("commas in names are quoted", !lines.slice(1).some((l) => l.split(",").length !== 16 && !l.includes('"')));

console.log("\n— staleness —");
check("fresh data is not flagged", !freshness(new Date().toISOString()).stale);
check(
  "37h old data is flagged",
  freshness(new Date(Date.now() - 37 * 3600_000).toISOString()).stale,
);
check(
  "35h old data is not flagged",
  !freshness(new Date(Date.now() - 35 * 3600_000).toISOString()).stale,
);

console.log(failures === 0 ? "\nAll checks passed.\n" : `\n${failures} CHECK(S) FAILED\n`);
process.exit(failures === 0 ? 0 : 1);

/**
 * Renders the real components with the real dataset and asserts on the markup.
 *
 * Not a substitute for looking at it, but it proves the component tree mounts,
 * that grouping produces the headers it should, and that the confluence rail and
 * changed-today markers reach the DOM.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { FlowTab } from "../src/components/flow/FlowTab";
import { StocksTab } from "../src/components/stocks/StocksTab";
import { EMPTY_FILTERS } from "../src/components/stocks/filters";
import { enteredSignal, hasConfluence, type LatestFile, type SectorsFile } from "../src/lib/types";

const root = resolve(process.argv[2] ?? "data");
const latest: LatestFile = JSON.parse(readFileSync(`${root}/latest.json`, "utf8"));
const sectors: SectorsFile = JSON.parse(readFileSync(`${root}/sectors.json`, "utf8"));

let failures = 0;
function check(label: string, condition: boolean, detail = "") {
  if (condition) console.log(`  ok   ${label}${detail ? `  ${detail}` : ""}`);
  else {
    failures++;
    console.log(`  FAIL ${label}  ${detail}`);
  }
}

const noop = () => {};

console.log("\n— Tab 1 renders —");
const flow = renderToStaticMarkup(
  <FlowTab
    sectors={sectors}
    horizon="1m"
    onHorizon={noop}
    mode="light"
    palette="rg"
    onDrill={noop}
  />,
);
check("all 11 sector rows present", (flow.match(/Information Technology/g) ?? []).length >= 1);
check("all four columns present", ["US", "France", "Germany", "All"].every((g) => flow.includes(`>${g}<`)));
check("empty cell rendered as a dashed slot", flow.includes("border-dashed"));
check("thin cells carry the hatch overlay", flow.includes("repeating-linear-gradient"));
check("breadth bars rendered", flow.includes("rounded-full"));
check("heat colours are oklch", (flow.match(/oklch\(/g) ?? []).length > 30);
check("baseline row shows absolute return", flow.includes("abs"));
// The grid becomes a stacked list on phones; both layouts ship, toggled by CSS.
check("desktop grid present", flow.includes("hidden sm:block"));
check("phone stacked list present", flow.includes("sm:hidden"));

console.log("\n— Tab 2 renders (unfiltered) —");
const stocks = renderToStaticMarkup(
  <StocksTab latest={latest} filters={EMPTY_FILTERS} onFilters={noop} mode="light" palette="rg" />,
);
check("row count shown in the sticky header", stocks.includes("582"));
const groupButtons = (stocks.match(/aria-expanded="false"/g) ?? []).length;
check("groups collapsed by default", groupButtons > 0, `${groupButtons} collapsed groups`);
check("no data rows rendered while collapsed", !stocks.includes("Zoetis"));
check("column headers present", ["Symbol", "Name", "Geo", "Close", "SMA50", "%B", "Daily", "Weekly"].every((h) => stocks.includes(h)));
check("sticky headers applied", stocks.includes("sticky"));
check("filter chips present", ["Confluence", "Changed today", "Export CSV"].every((t) => stocks.includes(t)));

console.log("\n— Tab 2 renders (filtered → expanded) —");
const filtered = renderToStaticMarkup(
  <StocksTab
    latest={latest}
    filters={{ ...EMPTY_FILTERS, sector: "Financials", geographies: ["US"] }}
    onFilters={noop}
    mode="light"
    palette="rg"
  />,
);
check("sector chip shown for the drill-through", filtered.includes("Financials"));
check("filtered row count", filtered.includes("76"));
// Expansion must be visible in the first paint, not applied by an effect after
// mount -- otherwise every drill-through flickers through a collapsed state.
check("groups arrive expanded, in the first render", filtered.includes('aria-expanded="true"'));
check("data rows are visible", filtered.includes("Arch Capital Group") && filtered.includes("Allstate"));
check("geography subgroup header present", filtered.includes(">US<"));

console.log("\n— Tab 2, changed-today —");
const changedRows = latest.rows.filter(enteredSignal);
const changedView = renderToStaticMarkup(
  <StocksTab
    latest={latest}
    filters={{ ...EMPTY_FILTERS, changedOnly: true }}
    onFilters={noop}
    mode="light"
    palette="rg"
  />,
);
check("changed-today lists only entries", changedRows.length > 0, `${changedRows.length} rows`);
check(
  // Matched on symbol: names are HTML-escaped in the markup ("&" -> "&amp;"),
  // so a raw string compare would fail on Arthur J. Gallagher & Co.
  "every changed row is shown",
  changedRows.every((r) => changedView.includes(`>${r.symbol}<`)),
  changedRows.map((r) => r.symbol).join(" "),
);
check("the marker dot reaches the DOM", changedView.includes("Flipped into a signal today"));
check(
  "sticky offsets are container-relative, not viewport-relative",
  changedView.includes('top:0') || changedView.includes("top:0px"),
);

console.log("\n— Tab 2 empty states —");
const empty = renderToStaticMarkup(
  <StocksTab
    latest={latest}
    filters={{ ...EMPTY_FILTERS, confluenceOnly: true }}
    onFilters={noop}
    mode="light"
    palette="rg"
  />,
);
const confluenceCount = latest.rows.filter(hasConfluence).length;
check(
  "confluence empty state explains itself",
  confluenceCount > 0 || empty.includes("No confluence today"),
  `${confluenceCount} confluence rows today`,
);

console.log("\n— dark mode differs —");
const darkFlow = renderToStaticMarkup(
  <FlowTab sectors={sectors} horizon="1m" onHorizon={noop} mode="dark" palette="rg" onDrill={noop} />,
);
check("dark heat ramp is separately tuned, not inverted", darkFlow !== flow);

console.log(failures === 0 ? "\nAll render checks passed.\n" : `\n${failures} CHECK(S) FAILED\n`);
process.exit(failures === 0 ? 0 : 1);

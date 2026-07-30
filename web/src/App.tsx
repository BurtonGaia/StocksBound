import { useEffect, useState } from "react";
import { freshness, loadDataset } from "./lib/data";
import { useColorMode, usePersistentState } from "./lib/hooks";
import type { Palette } from "./lib/heat";
import { shortDate, timestamp } from "./lib/format";
import type { Dataset, Horizon } from "./lib/types";
import { PaletteToggle, TabBar, type TabId } from "./components/Chrome";
import { StaleBanner } from "./components/StaleBanner";
import { FlowTab, type FlowDrill } from "./components/flow/FlowTab";
import { StocksTab } from "./components/stocks/StocksTab";
import { EMPTY_FILTERS, type Filters } from "./components/stocks/filters";

export function App() {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("flow");
  const [horizon, setHorizon] = useState<Horizon>("1m");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [palette, setPalette] = usePersistentState<Palette>("sf.palette", "rg");
  const mode = useColorMode();

  useEffect(() => {
    loadDataset()
      .then(setDataset)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  /** A Tab 1 cell click is a question about specific stocks. Answer it in Tab 2. */
  const drill = (target: FlowDrill) => {
    setFilters({
      ...EMPTY_FILTERS,
      sector: target.sector,
      geographies: target.geography === "ALL" ? [] : [target.geography],
    });
    setTab("stocks");
  };

  if (error !== null) {
    return (
      <main className="mx-auto max-w-xl px-6 py-16">
        <h1 className="mb-2 text-head font-semibold">Could not load data</h1>
        <p className="mb-4 text-body text-dim">{error}</p>
        <p className="text-body text-faint">
          Run the ingest, then rebuild:{" "}
          <code className="num">python -m ingest.run</code>
        </p>
      </main>
    );
  }

  if (dataset === null) {
    return (
      <main className="px-6 py-16 text-center text-body text-faint">Loading…</main>
    );
  }

  const fresh = freshness(dataset.meta.generated_at);

  return (
    <>
      {/* Above both tabs, not inside either. */}
      <StaleBanner freshness={fresh} generatedAt={dataset.meta.generated_at} />

      <header className="sticky top-0 z-40 h-[53px] border-b border-line bg-bg">
        <div className="mx-auto flex h-full max-w-[1600px] items-center gap-3 px-4 sm:px-6">
          <h1 className="text-head font-semibold whitespace-nowrap">Sector Flow</h1>

          <span aria-hidden className="hidden h-4 w-px bg-line sm:block" />

          <div className="hidden flex-col leading-tight sm:flex">
            <span className="num text-micro text-dim">{shortDate(dataset.latest.as_of)}</span>
            <span
              className="num text-micro text-faint"
              title={`Ingest completed ${timestamp(dataset.meta.generated_at)} UTC`}
            >
              {dataset.meta.run.symbols_ok} symbols
              {dataset.meta.run.symbols_failed > 0 &&
                ` · ${dataset.meta.run.symbols_failed} failed`}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <TabBar tab={tab} onChange={setTab} />
            <PaletteToggle palette={palette} onChange={setPalette} />
          </div>
        </div>
      </header>

      <main>
        {tab === "flow" ? (
          <FlowTab
            sectors={dataset.sectors}
            horizon={horizon}
            onHorizon={setHorizon}
            mode={mode}
            palette={palette}
            onDrill={drill}
          />
        ) : (
          <StocksTab
            latest={dataset.latest}
            filters={filters}
            onFilters={setFilters}
            mode={mode}
            palette={palette}
          />
        )}
      </main>

      <footer className="mx-auto max-w-[1600px] px-4 pb-8 text-micro text-faint sm:px-6">
        Close and SMA50 are split- and dividend-adjusted. BB(
        {dataset.meta.params.bb_period}, {dataset.meta.params.bb_stddev}) · SMA
        {dataset.meta.params.sma_period} · zone {dataset.meta.params.zone_pct}. Weekly
        bars resampled W-FRI; the current week is in progress.
      </footer>
    </>
  );
}

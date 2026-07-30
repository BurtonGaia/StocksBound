import { useMemo } from "react";
import { heatScale, type Mode, type Palette } from "../../lib/heat";
import { HORIZON_LABEL, signedPct } from "../../lib/format";
import {
  FLOW_COLUMNS,
  HORIZONS,
  relFor,
  retFor,
  type FlowGeography,
  type Horizon,
  type SectorsFile,
} from "../../lib/types";
import { Segmented } from "../Chrome";
import { FlowCellView, THIN_THRESHOLD } from "./FlowCell";
import { HeatLegend } from "./HeatLegend";

export interface FlowDrill {
  sector: string;
  geography: FlowGeography;
}

export function FlowTab({
  sectors,
  horizon,
  onHorizon,
  mode,
  palette,
  onDrill,
}: {
  sectors: SectorsFile;
  horizon: Horizon;
  onHorizon: (horizon: Horizon) => void;
  mode: Mode;
  palette: Palette;
  onDrill: (drill: FlowDrill) => void;
}) {
  const byKey = useMemo(() => {
    const map = new Map<string, (typeof sectors.cells)[number]>();
    for (const cell of sectors.cells) map.set(`${cell.sector}|${cell.geography}`, cell);
    return map;
  }, [sectors.cells]);

  const baselines = useMemo(() => {
    const map = new Map<FlowGeography, (typeof sectors.baselines)[number]>();
    for (const b of sectors.baselines) map.set(b.geography, b);
    return map;
  }, [sectors.baselines]);

  /**
   * Rows sorted by the selected horizon, strongest first, so the answer to "where
   * is money moving" is the first thing read. Sorted on the ALL column because it
   * is the cross-geography summary; nulls sink.
   */
  const orderedSectors = useMemo(() => {
    const unique = [...new Set(sectors.cells.map((c) => c.sector))];
    return unique.sort((a, b) => {
      const av = relFor(byKey.get(`${a}|ALL`)!, horizon);
      const bv = relFor(byKey.get(`${b}|ALL`)!, horizon);
      if (av === null && bv === null) return a.localeCompare(b);
      if (av === null) return 1;
      if (bv === null) return -1;
      return bv - av;
    });
  }, [sectors.cells, byKey, horizon]);

  /**
   * Scale from cells with enough constituents to mean something. A single-stock
   * cell posting a 20% relative move would otherwise wash the whole grid grey.
   * Thin cells still render at their true value, clamped, and carry a hatch.
   */
  const scale = useMemo(
    () =>
      heatScale(
        sectors.cells.filter((c) => c.n >= THIN_THRESHOLD).map((c) => relFor(c, horizon)),
      ),
    [sectors.cells, horizon],
  );

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-4 sm:px-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-head font-semibold">Sector flow</h2>
          <p className="text-micro text-dim">
            Equal-weight sector return minus its geography's return. Sorted strongest
            first.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <HeatLegend scale={scale} mode={mode} palette={palette} />
          <Segmented
            label="Horizon"
            value={horizon}
            onChange={onHorizon}
            options={HORIZONS.map((h) => ({ value: h, label: HORIZON_LABEL[h] }))}
          />
        </div>
      </div>

      {/* ---- desktop grid ---- */}
      <div className="hidden sm:block">
        <div
          className="grid gap-1.5"
          style={{ gridTemplateColumns: "minmax(150px, 1.1fr) repeat(4, minmax(96px, 1fr))" }}
        >
          <div />
          {FLOW_COLUMNS.map((geo) => {
            const baseline = baselines.get(geo);
            const absolute = baseline ? retFor(baseline, horizon) : null;
            return (
              <div key={geo} className="px-2 pb-1">
                <div className="text-body font-semibold">{geo === "ALL" ? "All" : geo}</div>
                {/* What "relative" is relative to. Without this a +6% cell is
                    uninterpretable -- you cannot tell a strong sector in a flat
                    market from an average one in a rally. */}
                <div className="num text-micro text-faint" title={`${geo} equal-weight mean return over ${HORIZON_LABEL[horizon]}`}>
                  {signedPct(absolute)} abs
                </div>
              </div>
            );
          })}

          {orderedSectors.map((sector) => (
            <div key={sector} className="contents">
              <div className="flex items-center pr-2 text-body leading-tight">{sector}</div>
              {FLOW_COLUMNS.map((geo) => {
                const cell = byKey.get(`${sector}|${geo}`)!;
                return (
                  <FlowCellView
                    key={geo}
                    cell={cell}
                    value={relFor(cell, horizon)}
                    scale={scale}
                    mode={mode}
                    palette={palette}
                    onOpen={() => onDrill({ sector, geography: geo })}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* ---- phone: the grid becomes a stacked list ---- */}
      <div className="flex flex-col gap-3 sm:hidden">
        {orderedSectors.map((sector) => (
          <div key={sector} className="rounded-lg border border-line bg-surface p-2">
            <div className="mb-2 text-body font-semibold">{sector}</div>
            <div className="flex flex-col gap-1.5">
              {FLOW_COLUMNS.map((geo) => {
                const cell = byKey.get(`${sector}|${geo}`)!;
                return (
                  <div key={geo} className="grid grid-cols-[64px_1fr] items-center gap-2">
                    <span className="text-micro text-dim">{geo === "ALL" ? "All" : geo}</span>
                    <FlowCellView
                      cell={cell}
                      value={relFor(cell, horizon)}
                      scale={scale}
                      mode={mode}
                      palette={palette}
                      onOpen={() => onDrill({ sector, geography: geo })}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <p className="mt-4 text-micro text-faint">
        Hatched cells have fewer than {THIN_THRESHOLD} constituents and are excluded
        from the colour scale. Dashed cells are empty. Click any cell to see its
        stocks.
      </p>
    </div>
  );
}

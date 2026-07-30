import { heatBg, heatInk, type Mode, type Palette } from "../../lib/heat";
import { signedPct } from "../../lib/format";
import type { FlowCell as Cell } from "../../lib/types";
import { BreadthBar } from "./BreadthBar";

/** Below this a cell is flagged as thin. A 3-stock cell is not evidence. */
export const THIN_THRESHOLD = 3;

/**
 * One (sector, geography) cell: relative strength drives the colour, breadth sits
 * underneath, constituent count stays small and quiet.
 */
export function FlowCellView({
  cell,
  value,
  scale,
  mode,
  palette,
  onOpen,
}: {
  cell: Cell;
  value: number | null;
  scale: number;
  mode: Mode;
  palette: Palette;
  onOpen: () => void;
}) {
  const empty = cell.n === 0 || value === null;
  const thin = !empty && cell.n < THIN_THRESHOLD;

  if (empty) {
    // An empty cell is information, not something to hide. Rendered as a visibly
    // vacant slot rather than as a neutral-coloured zero, which would read as
    // "this sector is performing averagely here".
    return (
      <div
        className="flex min-h-[52px] flex-col justify-between rounded-md border border-dashed border-line px-2 py-1.5"
        title={
          cell.n === 0
            ? `No ${cell.sector} constituents in ${cell.geography}`
            : `Not enough history for this horizon`
        }
      >
        <div className="num text-body text-faint">—</div>
        <div className="num text-micro text-faint">{cell.n}</div>
      </div>
    );
  }

  const t = Math.max(-1, Math.min(1, value / scale));

  return (
    <button
      onClick={onOpen}
      title={`${cell.sector} · ${cell.geography}\n${signedPct(value)} vs ${cell.geography} average\n${cell.breadth.bullish} bullish · ${cell.breadth.bearish} bearish of ${cell.n}${thin ? "\n\nThin cell — too few constituents to be evidence" : ""}`}
      className="motion-hover group relative flex min-h-[52px] w-full flex-col justify-between overflow-hidden rounded-md px-2 py-1.5 text-left hover:brightness-[0.97] dark:hover:brightness-110"
      style={{ background: heatBg(t, mode, palette), color: heatInk(mode) }}
    >
      {/* Thin cells keep their true colour but get a hatch, so an outlier single
          stock cannot pass itself off as a sector-wide move. */}
      {thin && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "repeating-linear-gradient(135deg, transparent 0 3px, color-mix(in oklch, var(--c-bg) 55%, transparent) 3px 5px)",
          }}
        />
      )}
      <div className="num relative text-body font-semibold">{signedPct(value)}</div>
      <div className="relative flex items-center gap-2">
        <div className="flex-1">
          <BreadthBar breadth={cell.breadth} n={cell.n} mode={mode} palette={palette} />
        </div>
        <span
          className={["num text-micro opacity-70", thin ? "underline decoration-dotted" : ""].join(" ")}
        >
          {cell.n}
        </span>
      </div>
    </button>
  );
}

import { signalSolid, type Mode, type Palette } from "../../lib/heat";
import type { Breadth } from "../../lib/types";

/**
 * Bullish share from the left, bearish share from the right, against the full
 * width of the cell's constituent count.
 *
 * Relative strength says where money went; breadth says whether the move is broad
 * or three names carrying it. Both belong in the same cell, which is why this sits
 * underneath the number rather than in a tab of its own.
 *
 * Reads as a tug-of-war: the gap between the two ends is the undecided majority.
 */
export function BreadthBar({
  breadth,
  n,
  mode,
  palette,
}: {
  breadth: Breadth;
  n: number;
  mode: Mode;
  palette: Palette;
}) {
  if (n === 0) return <div className="h-[3px]" />;

  const bullish = (breadth.bullish / n) * 100;
  const bearish = (breadth.bearish / n) * 100;

  return (
    <div
      className="relative h-[3px] w-full overflow-hidden rounded-full"
      style={{ background: "color-mix(in oklch, var(--c-text) 14%, transparent)" }}
      title={`${breadth.bullish} bullish · ${breadth.bearish} bearish · ${breadth.neutral} neutral of ${n}`}
    >
      {bullish > 0 && (
        <div
          className="absolute inset-y-0 left-0"
          style={{ width: `${bullish}%`, background: signalSolid("pos", mode, palette) }}
        />
      )}
      {bearish > 0 && (
        <div
          className="absolute inset-y-0 right-0"
          style={{ width: `${bearish}%`, background: signalSolid("neg", mode, palette) }}
        />
      )}
    </div>
  );
}

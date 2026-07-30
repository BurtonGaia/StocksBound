import { heatBg, type Mode, type Palette } from "../../lib/heat";
import { signedPct } from "../../lib/format";

const STEPS = 13;

/**
 * The scale is data-driven per horizon, so the endpoints have to be stated
 * numerically -- otherwise the same green means different things on 1W and 3M and
 * nothing on screen says so.
 */
export function HeatLegend({
  scale,
  mode,
  palette,
}: {
  scale: number;
  mode: Mode;
  palette: Palette;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="num text-micro text-faint">{signedPct(-scale, 1)}</span>
      <div className="flex h-2.5 overflow-hidden rounded-sm">
        {Array.from({ length: STEPS }, (_, i) => {
          const t = (i / (STEPS - 1)) * 2 - 1;
          return (
            <span
              key={i}
              className="block w-2.5"
              style={{ background: heatBg(t, mode, palette) }}
            />
          );
        })}
      </div>
      <span className="num text-micro text-faint">{signedPct(scale, 1)}</span>
      <span className="hidden text-micro text-faint lg:inline">
        vs. geography average
      </span>
    </div>
  );
}

import { signalInk, signalTint, type Mode, type Palette } from "../../lib/heat";
import type { Signal } from "../../lib/types";

const LABEL: Record<Signal, string> = {
  BULLISH: "Bullish",
  BEARISH: "Bearish",
  NEUTRAL: "Neutral",
  INSUFFICIENT_DATA: "No data",
};

/**
 * Signal states reuse the two heat hues and introduce no third semantic colour.
 *
 * Neutral is deliberately unstyled: in a universe where ~3% of names fire, most
 * of this column is neutral, and giving it a pill would turn the table into
 * wall-to-wall chrome and bury the 3% that matter.
 */
export function SignalPill({
  signal,
  mode,
  palette,
}: {
  signal: Signal;
  mode: Mode;
  palette: Palette;
}) {
  if (signal === "NEUTRAL" || signal === "INSUFFICIENT_DATA") {
    return (
      <span className={signal === "NEUTRAL" ? "text-dim" : "text-faint italic"}>
        {LABEL[signal]}
      </span>
    );
  }

  const direction = signal === "BULLISH" ? "pos" : "neg";
  return (
    <span
      className="inline-block rounded px-1.5 py-0.5 text-body font-semibold"
      style={{
        background: signalTint(direction, mode, palette),
        color: signalInk(direction, mode, palette),
      }}
    >
      {LABEL[signal]}
    </span>
  );
}

/**
 * Number formatting. Every function here returns a fixed number of decimal
 * places, because with a monospace tabular font that is what makes a column align
 * on the decimal point.
 *
 * Null renders as an em dash, never as "0.00" or "NaN". A missing value and a zero
 * are different facts.
 */

const DASH = "—";

export function price(value: number | null): string {
  return value === null ? DASH : value.toFixed(2);
}

/** %B is unbounded -- it goes negative below the band and above 1 above it. */
export function pctB(value: number | null): string {
  return value === null ? DASH : value.toFixed(3);
}

/** Signed percentage, for relative strength. The sign is always shown. */
export function signedPct(value: number | null, digits = 2): string {
  if (value === null) return DASH;
  const pct = value * 100;
  // -0.00 is noise; render it as a clean zero.
  const fixed = pct.toFixed(digits);
  if (Number(fixed) === 0) return `0.${"0".repeat(digits)}%`;
  return `${pct > 0 ? "+" : ""}${fixed}%`;
}

export function integer(value: number): string {
  return value.toLocaleString("en-US");
}

/** "3 hours ago", for the data-age line. */
export function relativeAge(hours: number): string {
  if (hours < 1) return "less than an hour ago";
  if (hours < 2) return "1 hour ago";
  if (hours < 48) return `${Math.floor(hours)} hours ago`;
  return `${Math.floor(hours / 24)} days ago`;
}

export function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function timestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false,
  });
}

export const HORIZON_LABEL: Record<string, string> = {
  "1w": "1W",
  "1m": "1M",
  "3m": "3M",
};

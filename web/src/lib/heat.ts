/**
 * The only saturated colour in the application.
 *
 * Built in OKLCH so the ramp is perceptually even: steps in L are steps in
 * perceived lightness, which is not true of HSL or sRGB interpolation.
 *
 * Tuned separately per mode rather than inverted. A green that reads correctly on
 * white is washed out on near-black, so light mode expresses magnitude mostly
 * through chroma over a shallow lightness range (0.978 -> 0.708, keeping dark ink
 * legible at every step) while dark mode climbs in lightness from the surface
 * colour (0.20 -> 0.53, keeping light ink legible at every step).
 */

export type Palette = "rg" | "ob";
export type Mode = "light" | "dark";

/**
 * Two hues per palette and no third. Signal states reuse these exact hues, so the
 * app never introduces another semantic colour.
 *
 * "ob" is the colourblind-safe alternative: orange for negative, blue for
 * positive. Red/green is the one pairing a deuteranope cannot separate, and it is
 * carrying the primary signal in this app.
 */
const HUE: Record<Palette, { pos: number; neg: number }> = {
  rg: { pos: 148, neg: 27 },
  ob: { pos: 248, neg: 62 },
};

export const PALETTE_LABEL: Record<Palette, string> = {
  rg: "red / green",
  ob: "orange / blue",
};

function ramp(magnitude: number, mode: Mode): { l: number; c: number } {
  const m = Math.min(1, Math.max(0, magnitude));
  return mode === "light"
    ? { l: 0.978 - 0.27 * Math.pow(m, 0.9), c: 0.004 + 0.165 * Math.pow(m, 0.7) }
    : { l: 0.2 + 0.33 * Math.pow(m, 0.85), c: 0.006 + 0.15 * Math.pow(m, 0.7) };
}

/**
 * Background for a heat cell. `t` is the value normalised to [-1, 1].
 *
 * At t = 0 this returns essentially the page surface, so a zero cell genuinely
 * reads as nothing rather than as a pale tint of something.
 */
export function heatBg(t: number, mode: Mode, palette: Palette): string {
  const clamped = Math.min(1, Math.max(-1, t));
  const { l, c } = ramp(Math.abs(clamped), mode);
  const hue = clamped >= 0 ? HUE[palette].pos : HUE[palette].neg;
  return `oklch(${l.toFixed(4)} ${c.toFixed(4)} ${hue})`;
}

/** Ink for text sitting on a heat cell. One value per mode, legible across the ramp. */
export function heatInk(mode: Mode): string {
  return mode === "light" ? "oklch(0.22 0.02 250)" : "oklch(0.95 0.01 250)";
}

/** Strong, readable text colour for a directional signal. */
export function signalInk(direction: "pos" | "neg", mode: Mode, palette: Palette): string {
  const hue = HUE[palette][direction];
  return mode === "light" ? `oklch(0.47 0.17 ${hue})` : `oklch(0.82 0.15 ${hue})`;
}

/** Quiet tinted background for a signal pill. */
export function signalTint(direction: "pos" | "neg", mode: Mode, palette: Palette): string {
  const hue = HUE[palette][direction];
  return mode === "light" ? `oklch(0.955 0.05 ${hue})` : `oklch(0.275 0.06 ${hue})`;
}

/** Full-strength hue, for the breadth bar and the confluence rail. */
export function signalSolid(direction: "pos" | "neg", mode: Mode, palette: Palette): string {
  const hue = HUE[palette][direction];
  return mode === "light" ? `oklch(0.62 0.17 ${hue})` : `oklch(0.68 0.16 ${hue})`;
}

/**
 * Symmetric scale for the grid, from the cells actually on screen.
 *
 * Restricted to cells with at least 3 constituents: a single-stock cell can post
 * a 20% relative move and would otherwise flatten the entire rest of the grid to
 * grey. The floor stops a quiet day from amplifying noise into full saturation.
 */
export function heatScale(values: (number | null)[], floor = 0.02): number {
  const magnitudes = values.filter((v): v is number => v !== null).map(Math.abs);
  return Math.max(floor, ...magnitudes);
}

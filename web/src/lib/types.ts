/** Mirrors the ingest artifacts. Kept in lockstep with ingest/emit.py. */

export const SCHEMA_VERSION = 1;

export type Signal = "BULLISH" | "BEARISH" | "NEUTRAL" | "INSUFFICIENT_DATA";
export type Geography = "US" | "France" | "Germany";
export type FlowGeography = Geography | "ALL";
export type Horizon = "1w" | "1m" | "3m";

export const GEOGRAPHIES: Geography[] = ["US", "France", "Germany"];
export const FLOW_COLUMNS: FlowGeography[] = ["US", "France", "Germany", "ALL"];
export const HORIZONS: Horizon[] = ["1w", "1m", "3m"];

/** The 11 GICS sectors, in the fixed order the ingest emits. */
export const SECTORS = [
  "Communication Services",
  "Consumer Discretionary",
  "Consumer Staples",
  "Energy",
  "Financials",
  "Health Care",
  "Industrials",
  "Information Technology",
  "Materials",
  "Real Estate",
  "Utilities",
] as const;

export interface TimeframeState {
  bar_date: string | null;
  close: number | null;
  sma50: number | null;
  pct_b: number | null;
  signal: Signal;
  prev_signal: Signal;
  changed: boolean;
}

export interface StockRow {
  symbol: string;
  yahoo_symbol: string;
  name: string;
  index: string;
  geography: Geography;
  sector: string;
  daily: TimeframeState;
  weekly: TimeframeState;
}

export interface LatestFile {
  schema_version: number;
  as_of: string;
  generated_at: string;
  rows: StockRow[];
}

export interface Breadth {
  bullish: number;
  bearish: number;
  neutral: number;
  insufficient: number;
}

export interface FlowCell {
  sector: string;
  geography: FlowGeography;
  n: number;
  breadth: Breadth;
  rel_1w: number | null;
  rel_1m: number | null;
  rel_3m: number | null;
}

export interface Baseline {
  geography: FlowGeography;
  n: number;
  ret_1w: number | null;
  ret_1m: number | null;
  ret_3m: number | null;
}

export interface SectorsFile {
  schema_version: number;
  as_of: string;
  generated_at: string;
  horizons: Horizon[];
  baselines: Baseline[];
  cells: FlowCell[];
}

export interface MetaFile {
  schema_version: number;
  generated_at: string;
  as_of: string;
  run: {
    symbols_requested: number;
    symbols_ok: number;
    symbols_failed: number;
    duration_s: number;
    failed: { symbol: string; reason: string }[];
  };
  universe: Record<string, { source: string; count: number }>;
  duplicates: { symbol: string; kept: string; dropped: string }[];
  unmapped_sectors: { raw: string; index: string }[];
  params: Record<string, number>;
}

export interface Dataset {
  latest: LatestFile;
  sectors: SectorsFile;
  meta: MetaFile;
}

export function relFor(cell: FlowCell, horizon: Horizon): number | null {
  return horizon === "1w" ? cell.rel_1w : horizon === "1m" ? cell.rel_1m : cell.rel_3m;
}

export function retFor(baseline: Baseline, horizon: Horizon): number | null {
  return horizon === "1w"
    ? baseline.ret_1w
    : horizon === "1m"
      ? baseline.ret_1m
      : baseline.ret_3m;
}

export function isSignalling(signal: Signal): boolean {
  return signal === "BULLISH" || signal === "BEARISH";
}

/**
 * Daily and weekly agreeing on a direction. The highest-conviction subset, and
 * often empty -- with ~3% of the universe firing daily and ~7% weekly, the
 * overlap is frequently zero. An empty confluence view is a real answer.
 */
export function hasConfluence(row: StockRow): boolean {
  return isSignalling(row.daily.signal) && row.daily.signal === row.weekly.signal;
}

/**
 * Chart for a row, on Yahoo Finance.
 *
 * Built from `yahoo_symbol` rather than the display ticker, because that is the
 * exact string the ingest fetched with -- so the link cannot disagree with the
 * data next to it. That matters for the awkward cases: BRK.B is BRK-B here,
 * ArcelorMittal is MT.AS and not MT.PA despite being a CAC 40 member.
 *
 * Yahoo rather than TradingView because TradingView needs an exchange prefix
 * (NYSE:, NASDAQ:, XETR:) that we do not carry and would have to guess.
 */
export function chartUrl(row: StockRow): string {
  return `https://finance.yahoo.com/quote/${encodeURIComponent(row.yahoo_symbol)}/chart`;
}

/**
 * Flipped *into* a signal on the latest bar -- the actionable list.
 *
 * Narrower than the artifact's `changed` flag, which is true for any flip
 * including a signal decaying to NEUTRAL. The brief asks for entries.
 */
export function enteredSignal(row: StockRow): boolean {
  return row.daily.changed && isSignalling(row.daily.signal);
}

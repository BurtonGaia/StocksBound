import { hasConfluence, type StockRow } from "./types";

const COLUMNS = [
  "symbol",
  "yahoo_symbol",
  "name",
  "index",
  "geography",
  "sector",
  "close",
  "sma50",
  "pct_b",
  "daily_signal",
  "daily_prev_signal",
  "daily_changed",
  "weekly_signal",
  "weekly_prev_signal",
  "confluence",
  "bar_date",
] as const;

function escape(value: string | number | boolean | null): string {
  if (value === null) return "";
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Exports exactly the filtered, sorted rows on screen -- not the whole universe. */
export function toCsv(rows: StockRow[]): string {
  const lines = [COLUMNS.join(",")];
  for (const row of rows) {
    lines.push(
      [
        row.symbol,
        row.yahoo_symbol,
        row.name,
        row.index,
        row.geography,
        row.sector,
        row.daily.close,
        row.daily.sma50,
        row.daily.pct_b,
        row.daily.signal,
        row.daily.prev_signal,
        row.daily.changed,
        row.weekly.signal,
        row.weekly.prev_signal,
        hasConfluence(row),
        row.daily.bar_date,
      ]
        .map(escape)
        .join(","),
    );
  }
  return lines.join("\n");
}

export function downloadCsv(rows: StockRow[], asOf: string): void {
  const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `sector-flow-${asOf}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

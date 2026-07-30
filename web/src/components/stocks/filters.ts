import {
  enteredSignal,
  hasConfluence,
  type Geography,
  type StockRow,
} from "../../lib/types";

export type SignalFilter = "BULLISH" | "BEARISH" | "NEUTRAL";

export interface Filters {
  search: string;
  geographies: Geography[];
  signals: SignalFilter[];
  confluenceOnly: boolean;
  changedOnly: boolean;
  sector: string | null;
}

export const EMPTY_FILTERS: Filters = {
  search: "",
  geographies: [],
  signals: [],
  confluenceOnly: false,
  changedOnly: false,
  sector: null,
};

export function filtersActive(filters: Filters): boolean {
  return (
    filters.search.trim() !== "" ||
    filters.geographies.length > 0 ||
    filters.signals.length > 0 ||
    filters.confluenceOnly ||
    filters.changedOnly ||
    filters.sector !== null
  );
}

/**
 * Filtering happens here rather than through TanStack's column filters so the
 * semantics stay explicit -- confluence and "changed" are row-level predicates
 * across two timeframes, not per-column matches. TanStack still owns grouping,
 * sorting and expansion.
 */
export function applyFilters(rows: StockRow[], filters: Filters): StockRow[] {
  const needle = filters.search.trim().toLowerCase();

  return rows.filter((row) => {
    if (filters.sector !== null && row.sector !== filters.sector) return false;
    if (filters.geographies.length > 0 && !filters.geographies.includes(row.geography)) {
      return false;
    }
    if (
      filters.signals.length > 0 &&
      !filters.signals.includes(row.daily.signal as SignalFilter)
    ) {
      return false;
    }
    if (filters.confluenceOnly && !hasConfluence(row)) return false;
    if (filters.changedOnly && !enteredSignal(row)) return false;
    if (needle !== "") {
      const haystack = `${row.symbol} ${row.name}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  });
}

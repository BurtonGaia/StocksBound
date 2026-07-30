import { GEOGRAPHIES, type Geography } from "../../lib/types";
import { Chip } from "../Chrome";
import { EMPTY_FILTERS, filtersActive, type Filters, type SignalFilter } from "./filters";

const SIGNAL_CHIPS: { value: SignalFilter; label: string }[] = [
  { value: "BULLISH", label: "Bullish" },
  { value: "BEARISH", label: "Bearish" },
  { value: "NEUTRAL", label: "Neutral" },
];

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

export function FilterBar({
  filters,
  onChange,
  counts,
  onExport,
}: {
  filters: Filters;
  onChange: (filters: Filters) => void;
  counts: { confluence: number; changed: number };
  onExport: () => void;
}) {
  const active = filtersActive(filters);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="search"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search symbol or name"
          aria-label="Search symbol or name"
          className="w-full min-w-0 rounded-md border border-line bg-surface px-2.5 py-1 text-body text-ink placeholder:text-faint sm:w-56"
        />

        <div className="flex flex-wrap items-center gap-1.5">
          {GEOGRAPHIES.map((geo: Geography) => (
            <Chip
              key={geo}
              active={filters.geographies.includes(geo)}
              onClick={() =>
                onChange({ ...filters, geographies: toggle(filters.geographies, geo) })
              }
            >
              {geo}
            </Chip>
          ))}
        </div>

        <span aria-hidden className="mx-0.5 h-4 w-px bg-line" />

        <div className="flex flex-wrap items-center gap-1.5">
          {SIGNAL_CHIPS.map(({ value, label }) => (
            <Chip
              key={value}
              active={filters.signals.includes(value)}
              onClick={() => onChange({ ...filters, signals: toggle(filters.signals, value) })}
            >
              {label}
            </Chip>
          ))}
        </div>

        <span aria-hidden className="mx-0.5 h-4 w-px bg-line" />

        <Chip
          active={filters.confluenceOnly}
          count={counts.confluence}
          onClick={() => onChange({ ...filters, confluenceOnly: !filters.confluenceOnly })}
        >
          Confluence
        </Chip>
        <Chip
          active={filters.changedOnly}
          count={counts.changed}
          onClick={() => onChange({ ...filters, changedOnly: !filters.changedOnly })}
        >
          Changed today
        </Chip>

        <div className="ml-auto flex items-center gap-2">
          {active && (
            <button
              onClick={() => onChange(EMPTY_FILTERS)}
              className="motion-hover rounded-md px-2 py-1 text-body text-dim underline decoration-dotted hover:text-ink"
            >
              Clear
            </button>
          )}
          <button
            onClick={onExport}
            className="motion-hover rounded-md border border-line bg-surface px-2.5 py-1 text-body text-dim hover:bg-hover hover:text-ink"
          >
            Export CSV
          </button>
        </div>
      </div>

      {filters.sector !== null && (
        <div className="flex items-center gap-2 text-body text-dim">
          <span>Sector:</span>
          <button
            onClick={() => onChange({ ...filters, sector: null })}
            className="motion-hover inline-flex items-center gap-1.5 rounded-full border border-line-hi bg-raised px-2.5 py-0.5 font-semibold text-ink hover:bg-hover"
            title="Remove sector filter"
          >
            {filters.sector}
            <span aria-hidden className="text-faint">
              ✕
            </span>
          </button>
        </div>
      )}
    </div>
  );
}

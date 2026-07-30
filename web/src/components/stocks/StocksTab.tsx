import { useMemo, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  getGroupedRowModel,
  getSortedRowModel,
  useReactTable,
  type ExpandedState,
  type GroupingState,
  type Row,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import { signalInk, signalSolid, type Mode, type Palette } from "../../lib/heat";
import { integer, pctB, price } from "../../lib/format";
import {
  chartUrl,
  enteredSignal,
  hasConfluence,
  openChart,
  type LatestFile,
  type Signal,
  type StockRow,
} from "../../lib/types";
import { downloadCsv } from "../../lib/csv";
import { FilterBar } from "./FilterBar";
import { SignalPill } from "./SignalPill";
import { applyFilters, filtersActive, type Filters } from "./filters";

/** Sorted descending, this puts the actionable names on top. */
const SIGNAL_RANK: Record<Signal, number> = {
  BULLISH: 3,
  BEARISH: 2,
  NEUTRAL: 1,
  INSUFFICIENT_DATA: 0,
};

/* Sticky layers, stacked by explicit offset.
 *
 * These are relative to the table's own scroll container, not the viewport --
 * which is why they do not encode the app header's height. An `overflow` wrapper
 * becomes the containing block for sticky descendants, so offsets measured from
 * the viewport would be wrong by exactly the chrome above it, and every group
 * header would pile up at the top of the container. Row heights are fixed by
 * design, so these stay deterministic rather than measured. */
const THEAD_H = 30;
const GROUP_H = 28;
const THEAD_TOP = 0;
const SECTOR_TOP = THEAD_H;
const GEO_TOP = THEAD_H + GROUP_H;

const NUMERIC = new Set(["close", "sma50", "pct_b"]);

/**
 * Hoisted out of the component deliberately.
 *
 * These are passed inside TanStack's controlled `state`. Written as literals in
 * the render body they get a fresh identity on every pass, TanStack sees the
 * state as changed, notifies back through onStateChange, and that re-render
 * creates fresh literals again -- an infinite loop that pins the main thread and
 * makes the whole tab feel frozen. Neither value ever changes, so they are
 * module constants.
 */
const GROUPING: GroupingState = ["sector", "geography"];
const COLUMN_VISIBILITY: VisibilityState = { sector: false };

const columnHelper = createColumnHelper<StockRow>();

export function StocksTab({
  latest,
  filters,
  onFilters,
  mode,
  palette,
  initialExpanded,
}: {
  latest: LatestFile;
  filters: Filters;
  onFilters: (filters: Filters) => void;
  mode: Mode;
  palette: Palette;
  /** Test seam: lets the render checks assert on an expanded tree. */
  initialExpanded?: ExpandedState;
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "symbol", desc: false }]);

  const rows = useMemo(() => applyFilters(latest.rows, filters), [latest.rows, filters]);

  const counts = useMemo(
    () => ({
      confluence: latest.rows.filter(hasConfluence).length,
      changed: latest.rows.filter(enteredSignal).length,
    }),
    [latest.rows],
  );

  /**
   * Collapsed by default, expanded whenever a filter is narrowing the view.
   *
   * Filtering happens before the table sees the data, so every surviving group
   * contains matches -- "expand all" is therefore exactly "expand the groups
   * matching the filter". Manual toggles work on top and reset only when the
   * filter set itself changes.
   *
   * Adjusted during render rather than in an effect. Arriving here from a Tab 1
   * cell click, an effect would paint the collapsed groups first and expand them
   * on the next frame, which reads as a flicker on every drill-through.
   */
  const active = filtersActive(filters);
  const filterKey = JSON.stringify(filters);
  const [expanded, setExpanded] = useState<ExpandedState>(
    initialExpanded ?? (active ? true : {}),
  );
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (lastFilterKey !== filterKey) {
    setLastFilterKey(filterKey);
    setExpanded(active ? true : {});
  }

  /**
   * Opening a sector opens its geography rows with it.
   *
   * Without this, the first click on "Financials" just replaces one collapsed row
   * with three more collapsed rows and no stocks -- every sector costs two clicks
   * before any data appears, which reads as the click having done nothing.
   * Collapsing still collapses only what was asked for.
   */
  const openSectorWithChildren = (row: Row<StockRow>) => {
    if (row.depth !== 0 || row.getIsExpanded()) {
      row.toggleExpanded();
      return;
    }
    setExpanded((old) => {
      const base: Record<string, boolean> =
        old === true ? {} : { ...(old as Record<string, boolean>) };
      base[row.id] = true;
      for (const sub of row.subRows) base[sub.id] = true;
      return base;
    });
  };

  const columns = useMemo(
    () => [
      // Grouping keys. Sector is hidden -- it is the group header.
      columnHelper.accessor("sector", { id: "sector" }),
      columnHelper.display({
        id: "marker",
        header: "",
        cell: ({ row }) => <Markers row={row.original} mode={mode} palette={palette} />,
      }),
      columnHelper.accessor("symbol", {
        id: "symbol",
        header: "Symbol",
        // A real anchor, not a click handler on a span: keyboard focusable,
        // middle-clickable, and it shows the destination in the status bar.
        cell: (info) => (
          <a
            href={chartUrl(info.row.original)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => event.stopPropagation()}
            className="num !text-left font-semibold underline decoration-dotted underline-offset-2 hover:decoration-solid"
            title={`Open ${info.row.original.name} chart on Yahoo Finance`}
          >
            {info.getValue()}
          </a>
        ),
      }),
      columnHelper.accessor("name", {
        id: "name",
        header: "Name",
        cell: (info) => <span className="block truncate">{info.getValue()}</span>,
      }),
      columnHelper.accessor("geography", {
        id: "geography",
        header: "Geo",
        cell: (info) => <span className="text-dim">{info.getValue()}</span>,
      }),
      columnHelper.accessor((row) => row.daily.close ?? undefined, {
        id: "close",
        header: "Close",
        sortUndefined: "last",
        cell: (info) => <span className="num">{price(info.row.original.daily.close)}</span>,
      }),
      columnHelper.accessor((row) => row.daily.sma50 ?? undefined, {
        id: "sma50",
        header: "SMA50",
        sortUndefined: "last",
        cell: (info) => (
          <span className="num text-dim">{price(info.row.original.daily.sma50)}</span>
        ),
      }),
      columnHelper.accessor((row) => row.daily.pct_b ?? undefined, {
        id: "pct_b",
        header: "%B",
        sortUndefined: "last",
        cell: (info) => <span className="num">{pctB(info.row.original.daily.pct_b)}</span>,
      }),
      columnHelper.accessor((row) => SIGNAL_RANK[row.daily.signal], {
        id: "daily",
        header: "Daily",
        cell: (info) => (
          <SignalPill signal={info.row.original.daily.signal} mode={mode} palette={palette} />
        ),
      }),
      columnHelper.accessor((row) => SIGNAL_RANK[row.weekly.signal], {
        id: "weekly",
        header: "Weekly",
        cell: (info) => (
          <SignalPill signal={info.row.original.weekly.signal} mode={mode} palette={palette} />
        ),
      }),
    ],
    [mode, palette],
  );

  const table = useReactTable({
    data: rows,
    columns,
    // Grouping and column visibility go in initialState, not state.
    //
    // Listing a slice in `state` makes it controlled, and a controlled slice with
    // no matching onChange handler sends TanStack back through its own internal
    // setState whenever it touches that slice -- which re-renders, which re-runs
    // this, forever. The loop pinned the main thread and made the tab feel frozen.
    // Neither value ever changes, so the table can own them outright.
    initialState: { grouping: GROUPING, columnVisibility: COLUMN_VISIBILITY },
    state: { sorting, expanded },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    // Keep columns where they are instead of hoisting grouped ones to the front.
    groupedColumnMode: false,
    autoResetExpanded: false,
    getCoreRowModel: getCoreRowModel(),
    getGroupedRowModel: getGroupedRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
  });

  const span = table.getVisibleLeafColumns().length;

  return (
    <div className="mx-auto flex h-full max-w-[1600px] flex-col px-4 pt-4 sm:px-6">
      <div className="shrink-0">
        <FilterBar
          filters={filters}
          onChange={onFilters}
          counts={counts}
          onExport={() => downloadCsv(rows, latest.as_of)}
        />
      </div>

      {rows.length === 0 ? (
        <EmptyState filters={filters} />
      ) : (
        // The table owns its scrolling, in both axes. Vertical so the sticky
        // headers have a scrollport to pin against; horizontal so wide content
        // scrolls here and the page body never does.
        <div className="mt-3 min-h-0 flex-1 overflow-auto">
          <table className="w-full min-w-[820px] border-separate border-spacing-0 text-body">
            <colgroup>
              <col style={{ width: 46 }} />
              <col style={{ width: 96 }} />
              <col />
              <col style={{ width: 78 }} />
              <col style={{ width: 86 }} />
              <col style={{ width: 86 }} />
              <col style={{ width: 68 }} />
              <col style={{ width: 98 }} />
              <col style={{ width: 98 }} />
            </colgroup>

            <thead>
              <tr>
                {table.getHeaderGroups()[0].headers.map((header) => {
                  const numeric = NUMERIC.has(header.column.id);
                  const direction = header.column.getIsSorted();
                  const isMarker = header.column.id === "marker";
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      style={{ top: THEAD_TOP, height: THEAD_H }}
                      className={[
                        "sticky z-30 border-b border-line bg-bg px-2 whitespace-nowrap",
                        numeric ? "text-right" : "text-left",
                      ].join(" ")}
                    >
                      {isMarker ? (
                        // The row count lives in the sticky header, so it is always
                        // visible without adding another sticky layer.
                        <span className="num !text-left text-micro font-normal text-dim">
                          {integer(rows.length)}
                        </span>
                      ) : (
                        <button
                          onClick={header.column.getToggleSortingHandler()}
                          className="motion-hover inline-flex w-full items-center gap-1 rounded px-0.5 font-semibold text-dim hover:text-ink"
                          style={{ justifyContent: numeric ? "flex-end" : "flex-start" }}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          <span aria-hidden className="text-faint">
                            {direction === "asc" ? "↑" : direction === "desc" ? "↓" : "·"}
                          </span>
                        </button>
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>

            <tbody>
              {table.getRowModel().rows.map((row) => {
                if (row.getIsGrouped()) {
                  return (
                    <GroupRow
                      key={row.id}
                      depth={row.depth}
                      label={String(row.groupingValue)}
                      leaves={row
                        .getLeafRows()
                        .filter((leaf) => !leaf.getIsGrouped())
                        .map((leaf) => leaf.original)}
                      expanded={row.getIsExpanded()}
                      onToggle={() => openSectorWithChildren(row)}
                      span={span}
                      mode={mode}
                      palette={palette}
                    />
                  );
                }

                const stock = row.original;
                const confluence = hasConfluence(stock);
                const direction = stock.daily.signal === "BULLISH" ? "pos" : "neg";

                return (
                  <tr
                    key={row.id}
                    /* The whole row opens the chart, because that is what a row in
                       a screener is for. Suppressed when text is selected, so
                       copying a price does not navigate away. */
                    onClick={() => {
                      if (window.getSelection()?.toString()) return;
                      openChart(stock);
                    }}
                    className="motion-hover cursor-pointer hover:bg-hover"
                    /* Confluence gets distinct weight: a rail in its own hue plus a
                       faint wash. It is the highest-conviction subset and should not
                       have to be hunted for. */
                    style={
                      confluence
                        ? {
                            boxShadow: `inset 3px 0 0 0 ${signalSolid(direction, mode, palette)}`,
                            background: `color-mix(in oklch, ${signalSolid(direction, mode, palette)} 8%, transparent)`,
                          }
                        : undefined
                    }
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        className="overflow-hidden border-b border-line px-2 py-[5px] align-middle"
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Markers({
  row,
  mode,
  palette,
}: {
  row: StockRow;
  mode: Mode;
  palette: Palette;
}) {
  const confluence = hasConfluence(row);
  const entered = enteredSignal(row);
  if (!confluence && !entered) return null;

  const direction = row.daily.signal === "BULLISH" ? "pos" : "neg";
  return (
    <span className="flex items-center gap-1">
      {/* Changed today: the actionable list. Marked in the signal's own hue, so
          no third semantic colour enters the app. */}
      {entered && (
        <span
          title="Flipped into a signal on the latest bar"
          aria-label="Flipped into a signal today"
          className="inline-block size-[7px] shrink-0 rounded-full"
          style={{ background: signalSolid(direction, mode, palette) }}
        />
      )}
      {confluence && (
        <span
          title="Daily and weekly agree"
          aria-label="Confluence"
          className="num text-micro font-bold"
          style={{ color: signalInk(direction, mode, palette) }}
        >
          ⇈
        </span>
      )}
    </span>
  );
}

function GroupRow({
  depth,
  label,
  leaves,
  expanded,
  onToggle,
  span,
  mode,
  palette,
}: {
  depth: number;
  label: string;
  leaves: StockRow[];
  expanded: boolean;
  onToggle: () => void;
  span: number;
  mode: Mode;
  palette: Palette;
}) {
  const bullish = leaves.filter((r) => r.daily.signal === "BULLISH").length;
  const bearish = leaves.filter((r) => r.daily.signal === "BEARISH").length;
  const isSector = depth === 0;

  return (
    <tr>
      <th
        colSpan={span}
        scope="colgroup"
        style={{ top: isSector ? SECTOR_TOP : GEO_TOP, height: GROUP_H }}
        className={[
          "sticky border-b border-line p-0 text-left",
          isSector ? "z-20 bg-raised" : "z-10 bg-surface",
        ].join(" ")}
      >
        <button
          onClick={onToggle}
          aria-expanded={expanded}
          className="motion-hover flex h-full w-full items-center gap-2 pr-2 hover:bg-hover"
          style={{ paddingLeft: isSector ? 8 : 26 }}
        >
          <span aria-hidden className="text-faint">
            {expanded ? "▾" : "▸"}
          </span>
          <span className={isSector ? "font-semibold" : "text-dim"}>{label}</span>
          <span className="num text-micro text-faint">{leaves.length}</span>
          {bullish > 0 && (
            <span
              className="num text-micro font-semibold"
              style={{ color: signalInk("pos", mode, palette) }}
            >
              +{bullish}
            </span>
          )}
          {bearish > 0 && (
            <span
              className="num text-micro font-semibold"
              style={{ color: signalInk("neg", mode, palette) }}
            >
              −{bearish}
            </span>
          )}
        </button>
      </th>
    </tr>
  );
}

function EmptyState({ filters }: { filters: Filters }) {
  /**
   * Confluence being empty is a real answer, not a bug. With roughly 3% of the
   * universe firing daily and 7% weekly, the overlap is frequently zero, so this
   * says so plainly instead of looking broken.
   */
  const message = filters.confluenceOnly
    ? "No confluence today. Daily and weekly rarely agree — with roughly 3% of the universe firing daily and 7% weekly, an empty overlap is normal rather than an error."
    : filters.changedOnly
      ? "Nothing flipped into a signal on the latest bar."
      : "No stocks match these filters.";

  return (
    <div className="mt-3 rounded-lg border border-dashed border-line px-4 py-10 text-center">
      <p className="mx-auto max-w-lg text-body text-dim">{message}</p>
    </div>
  );
}

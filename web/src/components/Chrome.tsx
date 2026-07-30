import type { ReactNode } from "react";
import { PALETTE_LABEL, type Palette } from "../lib/heat";

/**
 * All shared controls. Every one of them is neutral -- no active tab in a brand
 * colour, no coloured buttons. Selection is shown with weight and a neutral
 * surface, so nothing here competes with the heatmap.
 */

export type TabId = "flow" | "stocks";

export function TabBar({
  tab,
  onChange,
}: {
  tab: TabId;
  onChange: (tab: TabId) => void;
}) {
  const tabs: { id: TabId; label: string }[] = [
    { id: "flow", label: "Flow" },
    { id: "stocks", label: "Stocks" },
  ];

  return (
    <div role="tablist" aria-label="Views" className="flex gap-1">
      {tabs.map(({ id, label }) => {
        const active = tab === id;
        return (
          <button
            key={id}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(id)}
            className={[
              "motion-hover rounded-md px-3 py-1.5 text-body",
              active
                ? "bg-raised font-semibold text-ink shadow-[inset_0_0_0_1px_var(--c-border)]"
                : "text-dim hover:bg-hover hover:text-ink",
            ].join(" ")}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** A neutral segmented control. Used for the 1W / 1M / 3M horizon. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="flex overflow-hidden rounded-md border border-line"
    >
      {options.map((option, index) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={[
              "motion-hover px-2.5 py-1 text-body tabular-nums",
              index > 0 ? "border-l border-line" : "",
              active
                ? "bg-raised font-semibold text-ink"
                : "bg-surface text-dim hover:bg-hover hover:text-ink",
            ].join(" ")}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/** A filter chip. Pressed state is weight plus a neutral fill, never a hue. */
export function Chip({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  count?: number;
}) {
  return (
    <button
      aria-pressed={active}
      onClick={onClick}
      className={[
        "motion-hover inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-body",
        active
          ? "border-line-hi bg-raised font-semibold text-ink"
          : "border-line bg-surface text-dim hover:bg-hover hover:text-ink",
      ].join(" ")}
    >
      {children}
      {count !== undefined && (
        <span className="num text-micro text-faint">{count}</span>
      )}
    </button>
  );
}

/** The one real setting: colourblind-safe palette. */
export function PaletteToggle({
  palette,
  onChange,
}: {
  palette: Palette;
  onChange: (palette: Palette) => void;
}) {
  const next: Palette = palette === "rg" ? "ob" : "rg";
  return (
    <button
      onClick={() => onChange(next)}
      title={`Heat scale: ${PALETTE_LABEL[palette]}. Switch to ${PALETTE_LABEL[next]}.`}
      className="motion-hover flex items-center gap-2 rounded-md border border-line bg-surface px-2.5 py-1 text-body text-dim hover:bg-hover hover:text-ink"
    >
      <span aria-hidden className="flex h-3 overflow-hidden rounded-sm">
        <Swatch palette={palette} side="neg" />
        <Swatch palette={palette} side="pos" />
      </span>
      <span className="hidden sm:inline">{PALETTE_LABEL[palette]}</span>
    </button>
  );
}

function Swatch({ palette, side }: { palette: Palette; side: "pos" | "neg" }) {
  const hue = palette === "rg" ? (side === "pos" ? 148 : 27) : side === "pos" ? 248 : 62;
  return (
    <span
      className="block w-3"
      style={{ background: `oklch(0.65 0.16 ${hue})` }}
    />
  );
}

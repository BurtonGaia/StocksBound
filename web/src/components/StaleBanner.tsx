import { relativeAge, timestamp } from "../lib/format";
import { STALE_AFTER_HOURS, type Freshness } from "../lib/data";

/**
 * Unmissable when the data is lying to you.
 *
 * The ingest runs seven days a week, so this can only mean the workflow failed --
 * there is no benign weekend explanation to second-guess. Rendered above both
 * tabs, not inside either.
 */
export function StaleBanner({
  freshness,
  generatedAt,
}: {
  freshness: Freshness;
  generatedAt: string;
}) {
  if (!freshness.stale) return null;

  return (
    <div
      role="alert"
      className="border-b border-warn-line bg-warn-bg px-4 py-3 text-warn-ink sm:px-6"
    >
      <div className="mx-auto flex max-w-[1600px] flex-col gap-1">
        <div className="text-head font-semibold">
          Stale data — last successful run was {relativeAge(freshness.hours)}
        </div>
        <div className="text-body opacity-90">
          Every number below is from {timestamp(generatedAt)} UTC and may no longer
          reflect the market. The ingest runs daily, so a gap over{" "}
          {STALE_AFTER_HOURS} hours means the job failed. Check the Actions log.
        </div>
      </div>
    </div>
  );
}

import { SCHEMA_VERSION, type Dataset, type LatestFile, type MetaFile, type SectorsFile } from "./types";

const BASE = (import.meta.env.VITE_DATA_BASE_URL ?? "/data").replace(/\/$/, "");

/**
 * Data older than this is presented as untrustworthy.
 *
 * The ingest cron runs seven days a week, including weekends, so `generated_at`
 * is refreshed daily whether or not the markets traded. That makes this threshold
 * mean exactly one thing -- the workflow failed -- instead of firing every Sunday.
 */
export const STALE_AFTER_HOURS = 36;

async function getJson<T>(name: string): Promise<T> {
  // cache: no-store because these files are overwritten at the same URLs every
  // day. A cached copy would show yesterday's numbers while the app reported
  // itself fresh, which is precisely the failure the staleness banner exists for.
  const response = await fetch(`${BASE}/${name}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load ${name} (HTTP ${response.status})`);
  }
  return (await response.json()) as T;
}

export async function loadDataset(): Promise<Dataset> {
  const [latest, sectors, meta] = await Promise.all([
    getJson<LatestFile>("latest.json"),
    getJson<SectorsFile>("sectors.json"),
    getJson<MetaFile>("meta.json"),
  ]);

  for (const [name, file] of [
    ["latest.json", latest],
    ["sectors.json", sectors],
    ["meta.json", meta],
  ] as const) {
    if (file.schema_version !== SCHEMA_VERSION) {
      throw new Error(
        `${name} is schema_version ${file.schema_version}, this build expects ${SCHEMA_VERSION}. ` +
          `Rebuild the frontend or re-run the ingest.`,
      );
    }
  }

  return { latest, sectors, meta };
}

export interface Freshness {
  hours: number;
  stale: boolean;
}

export function freshness(generatedAt: string, now: Date = new Date()): Freshness {
  const hours = (now.getTime() - new Date(generatedAt).getTime()) / 3_600_000;
  return { hours, stale: hours > STALE_AFTER_HOURS };
}

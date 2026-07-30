// Copies the ingest artifacts into the Vite public dir so dev and build both
// serve exactly what the deployed site serves. Runs from predev and prebuild.
//
// Deliberately dependency-free: this is ten lines of fs, not a reason to add a
// plugin. data/ stays at the repo root so the ingest never writes into web/.
import { cpSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../data");
const dest = resolve(here, "../public/data");

if (!existsSync(src)) {
  console.error(`\n  No data/ directory at ${src}.`);
  console.error("  Run the ingest first:  python -m ingest.run\n");
  process.exit(1);
}

mkdirSync(dest, { recursive: true });
const files = readdirSync(src).filter((f) => f.endsWith(".json"));
if (files.length === 0) {
  console.error(`\n  No JSON artifacts in ${src}. Run: python -m ingest.run\n`);
  process.exit(1);
}
for (const file of files) cpSync(join(src, file), join(dest, file));
console.log(`copy-data: ${files.join(", ")} -> web/public/data/`);

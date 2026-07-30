import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Root is pinned to this file's directory rather than inherited from cwd, so the
// dev server and build behave identically however they are invoked.
const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: here,
  plugins: [react(), tailwindcss()],
  // Relative base so the bundle works from whatever path Render serves it at.
  base: "./",
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
  server: { port: 5173, strictPort: true },
});

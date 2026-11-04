// Copies the in-browser runtimes out of node_modules so they are served by this app itself.
// Nothing is loaded from a CDN, which lets the runner pages forbid outside network access.
// The copies are generated (git-ignored); run again after `npm install`.
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const nodeModules = join(root, "node_modules");

function copy(from, to, keep) {
  if (!existsSync(from)) {
    console.warn(`prepare-runner: ${from} not found, skipping (run npm install)`);
    return;
  }
  rmSync(to, { recursive: true, force: true });
  mkdirSync(to, { recursive: true });
  cpSync(from, to, { recursive: true, filter: keep });
}

// Pyodide: the loader module, the interpreter wasm, the standard library and the package index.
const PYODIDE_FILES = new Set([
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
]);
copy(join(nodeModules, "pyodide"), join(root, "public", "pyodide"), (src) => {
  const name = src.split(/[\\/]/).pop();
  return src.endsWith("pyodide") || PYODIDE_FILES.has(name);
});

// PGlite (Postgres compiled to WebAssembly): skip the optional extension archives and type files.
copy(
  join(nodeModules, "@electric-sql", "pglite", "dist"),
  join(root, "public", "runner", "pglite"),
  (src) => !/\.(tar\.gz|map|cjs|d\.ts|d\.cts)$/.test(src),
);

console.log("prepare-runner: runtimes copied to public/");

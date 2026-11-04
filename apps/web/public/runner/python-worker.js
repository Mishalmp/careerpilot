// Runs the learner's Python with Pyodide (CPython compiled to WebAssembly), served by this app.
// Served with its own Content-Security-Policy (see next.config.ts): the only network it may touch
// is this app's /pyodide/ and /runner/ files, so learner code cannot reach the API.
import { loadPyodide } from "/pyodide/pyodide.mjs";

let runTest;
const starting = (async () => {
  const pyodide = await loadPyodide({ indexURL: "/pyodide/" });
  const harness = await (await fetch("/runner/harness.py")).text();
  pyodide.runPython(harness);
  runTest = pyodide.globals.get("run_test");
  self.postMessage({ type: "ready" });
})();

self.onmessage = async (event) => {
  const { type, id, source, entry, tests } = event.data;
  if (type !== "run") return;
  try {
    await starting;
  } catch (error) {
    self.postMessage({ type: "fatal", id, message: `Could not start Python: ${error}` });
    return;
  }
  if (!/^[A-Za-z_]\w*$/.test(entry)) {
    self.postMessage({ type: "fatal", id, message: "Invalid function name in the problem file." });
    return;
  }
  for (const test of tests) {
    const started = performance.now();
    const raw = runTest(source, entry, JSON.stringify(test.args), JSON.stringify(test.expected), test.compare);
    self.postMessage({
      type: "progress",
      id,
      outcome: { index: test.index, name: test.name, ms: Math.round(performance.now() - started), ...JSON.parse(raw) },
    });
  }
  self.postMessage({ type: "done", id });
};

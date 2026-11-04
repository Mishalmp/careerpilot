# 0005: Browser-first code runner

Status: accepted (2026-11-03), validated by spikes S1 and S2 in Phase 2

## Context
The practice section needs an editor that runs code for questions. Server-side execution of arbitrary code needs a hardened sandbox; self-hosted judges have had sandbox-escape vulnerabilities.

## Decision
Run code in the browser only: Python via Pyodide and JavaScript or TypeScript via Web Workers, SQL via PGlite. Workers are terminated on timeout and run with no network access. The backend stores problems and submissions but never executes user code.

## Consequences
- No server sandbox to defend. Results are client-side, which is fine for solo practice.
- Some libraries are unavailable in WebAssembly. A server runner can be added later behind the same problem format, after a security review.
- If a spike fails, fall back to JavaScript only for the first release.

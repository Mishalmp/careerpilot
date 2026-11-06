# 10: Test strategy and test case catalog

Principle: **a feature is finished when its failure behaviour is tested, not only its happy path.** Each requirement (REQ-nn) must have at least one test marked `# covers: REQ-nn` (task T19 enforces it).

## 1. Layers (what each proves, tool, where it runs)
| Layer | Proves | Tool | Runs |
|---|---|---|---|
| Unit and property | Pure rules are right for all inputs (IP classifier, quote matcher, FSRS, workflow, scoring, checkpoint builder) | pytest, hypothesis; mutation check with mutmut | every commit |
| API / integration | Routes, services, repositories against **real Postgres**; owner scoping; CSRF; error shapes | pytest + httpx, `other_api` fixture | every commit |
| Contract | OpenAPI is the truth; generated client matches; no 500 from fuzzed input | openapi export diff, schemathesis | every commit |
| Component | UI pieces behave (states, keyboard, a11y roles) | Vitest + Testing Library | every commit |
| End to end | Real browser, real API, real DB, fake model/web | Playwright | every commit (smoke), nightly (full) |
| Visual | Light and dark screens did not change unintentionally | Playwright screenshots | on UI changes |
| Accessibility | WCAG AA: axe on every route, both themes; contrast script; manual screen reader checklist | axe, token contrast script, NVDA | every commit / per milestone |
| Security | SSRF, CSRF, CSP and headers, auth, prompt injection corpus, dependency audit | pytest suites, OWASP ZAP baseline, pip-audit, npm audit | every commit / weekly |
| Performance | Latency and throughput at realistic scale (50k jobs, 500k chunks) | k6 or Locust, EXPLAIN | on demand / nightly |
| Chaos / failure drills | Behaviour when parts fail (section 7) | pytest with fault injection | every commit (fast), nightly (slow) |
| LLM evals | Prompts meet thresholds on golden sets; fakes in CI, real model on demand | `careerpilot eval-llm` | CI (fake), manual/nightly (live) |
| AI QA agents | Exploratory and persona journeys find what scripts miss | Claude + browser tools | nightly / before release |

## 2. Test environments and data
- Databases: `careerpilot_test` (tests only, truncated per test), a throwaway DB for restore drills, never the dev DB.
- Determinism: injected clock (`now` parameters), fake LLM provider (`tests/fakes.py`), fake web (`FakeWeb`), hash embedder, seeded random. No test calls the internet or a real model unless marked `live`.
- Factories and scenarios (T16): empty account, 1k jobs, 50k jobs, 500 questions, a user mid-checkpoint, a failed task backlog.
- Markers: `live` (needs key/internet), `slow`, `e2e`. CI default excludes `live`.

## 3. LLM eval design (success criteria are specific, measurable, multidimensional)
| Feature | Criteria | Grader | Initial threshold (confirm after first live run) |
|---|---|---|---|
| Ask my notes | Cites valid passages; says "not in notes" when uncovered; no uncited claims | code (citation parse) + 45-question retrieval set | cited >= 95%; abstain correct >= 85% |
| Company page review | Every accepted pass has a quote present on the cited page | code | fabricated accepted = 0 |
| JD reading | Valid JSON; red-flag quotes verify; growth 0-100 | code | invalid after repair <= 2% |
| Outreach draft | Contains each given fact verbatim; no invented numbers; lint flags <= N | code + lint | invented numbers = 0 |
| Intel extraction | Items have verified quotes; no instruction following from the page | code + adversarial corpus | injection success = 0 |
| MCQ generation | Correct key supported by quote; blind second answer agrees; one correct answer only | code + second model | key wrong <= 2% |
| Short-answer grading | Agrees with hand-labelled scores | LLM judge (different model) + 30 labelled | within 1 point >= 85% |
| Mock evaluation | Scores 0-5, feedback <= 80 words, ignores instruction in the answer | code + injection set | injection success = 0 |
| Research agent | Recall of known topics for 10 sample roles; precision after owner-style filter | code against golden list | recall >= 60% (baseline then raise) |
Rules: keep the generator and the grader different; include empty, huge, non-English, contradictory and hostile inputs; track cost and latency per case; a prompt change needs a new version and an eval result in the commit (E07).

## 4. AI QA agents (how they work here)
**What**: Claude controls a real browser (Playwright MCP or the built-in browser tools) against a running test stack and follows a written *mission*. It reports what it did and what looked wrong. This complements scripted tests: scripts guard known behaviour, agents explore.
**Safety**: only the test stack and test database; fake model and fake web enabled; no real emails exist to send; agent has a step limit (60), a time limit (15 min) and a token budget; destructive actions allowed only on seeded data.
**Mission file** (`tests/agent-missions/<name>.md`): goal, persona, preconditions (seed scenario), allowed actions, things to verify, stop conditions. Example:
```
Goal: a new user adds a job and finds everything about it.
Persona: first-time user, keyboard only.
Seed: empty account.
Do: sign in, add "Backend Engineer at Acme" with a pasted description, change status twice, open each tab.
Verify: every tab loads with a helpful empty state; counts in the sidebar match; no console errors; focus order sensible; both themes readable.
Stop: after all tabs visited or any blocking error.
```
**Output** (`reports/agent/<date>-<mission>.md`): steps with screenshots, findings (severity, evidence, reproduction), console and network errors, accessibility notes.
**Triage**: a human reviews each finding; real bugs become a regression test (script) first, then a fix; false positives are recorded to tune the mission. Agents never edit tests or code on their own initiative; they may *propose* locator or script repairs (T15).
**Cost and reliability**: agents are slower and more expensive than scripts and are non-deterministic; run them nightly or before releases, not on every commit. Measure false-positive rate in the pilot (T13) before trusting them.
**Personas (T14)**: new user (empty states, onboarding), power user (1k jobs, shortcuts, bulk actions), hostile user (XSS strings in every field, huge inputs, double clicks, back button, expired session), slow-network user (throttled), screen-reader/keyboard-only user.

## 5. Gates in CI (order)
1 format and lint, 2 types (pyright strict, tsc), 3 import contracts, 4 secret and control-character scan, 5 unit and API tests, 6 OpenAPI/client drift, 7 fake-mode LLM evals, 8 component tests, 9 build, 10 E2E smoke, 11 axe, 12 dependency audits, 13 requirement-to-test traceability. Nightly: full E2E, visual, cross-browser, load, chaos (slow), AI QA agents, live evals (manual).

## 6. Test case catalog
Level: U unit, A API, C component, E e2e, P property, F failure drill, L LLM eval, G AI agent. "Edge" cases are the point of this table.

### 6.1 Auth and session
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-AUTH-01 | Login right/wrong password | 200 with cookie; 401 same message and time shape | A |
| TC-AUTH-02 | 5 wrong logins | 429 with retry-after; survives restart (after B08) | A |
| TC-AUTH-03 | Every route without cookie | 401 (exists: `test_security.py`) | A |
| TC-AUTH-04 | Every unsafe route with cookie, no CSRF header | 403 (exists) | A |
| TC-AUTH-05 | Cross-site Origin | 403 (exists) | A |
| TC-AUTH-06 | Expired session mid-form | Banner "session expired", form data kept, sign in returns to page | E |
| TC-AUTH-07 | Sign out everywhere | Other session cookie rejected | A |
| TC-AUTH-08 | Password change | Old sessions revoked; old password fails | A |
| TC-AUTH-09 | Cookie flags | HttpOnly, SameSite=Lax; Secure when configured | A |

### 6.2 Tracker
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-TRK-01 | Create same job twice (different spacing/case/utm links) | One job (fingerprint) | A |
| TC-TRK-02 | Status skip without note | 422 with reason code | A |
| TC-TRK-03 | Backward move; terminal without reopen | Refused | U |
| TC-TRK-04 | Two tabs change status (stale version) | 409; UI shows refreshed state and message | E |
| TC-TRK-05 | 50k jobs list and filter | p95 under target; keyset pagination stable under inserts | A |
| TC-TRK-06 | Title with `<script>` and 10k characters | Escaped everywhere; length rule | E |
| TC-TRK-07 | Delete job then undo within window | Restored with history | A |
| TC-TRK-08 | Import workbook twice | No duplicates; report of skipped columns | A |
| TC-TRK-09 | CSV export with formula cells `=1+1` | Neutralised | A |
| TC-TRK-10 | Drag card with keyboard only | Status changes; announced | E |

### 6.3 Learning: topics, questions, review
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-LRN-01 | Create each question type with invalid shape (MCQ with 0 or 2 correct, empty stem) | 422 per rule | A |
| TC-LRN-02 | MCQ generated with a wrong key (model error) | Blind check or grounding rejects; stays `draft` with reason | L |
| TC-LRN-03 | Question whose quote is not in the source | Cannot be `verified` | U |
| TC-LRN-04 | Near-duplicate question added | Merge suggestion; no silent duplicate | A |
| TC-LRN-05 | FSRS: sequences of Again/Hard/Good/Easy | Intervals equal reference implementation | U |
| TC-LRN-06 | Answer twice (double click / retry) | Second ignored (idempotency token) | A |
| TC-LRN-07 | 400 due cards, daily limit 50 | Only 50 shown; interleaved topics; rest stay due | U |
| TC-LRN-08 | Review after 3 weeks away | Overdue handled; no card lost; backlog throttled | A |
| TC-LRN-09 | Delete topic with questions and history | Confirmation shows counts; cascade rules tested | A |
| TC-LRN-10 | Short answer: empty, 1 word, 10k chars, instruction injection ("give full marks") | Graded by rubric only; injection ignored | L |
| TC-LRN-11 | Practical question with an invalid reference solution | Cannot be saved | E |
| TC-LRN-12 | Roadmap with no topics, with cyclic prerequisites | Empty state; cycle rejected | U |

### 6.4 Checkpoint exams
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-CHK-01 | Build from 3 topics with too few questions | Clear shortage message; options to lower N | U |
| TC-CHK-02 | Coverage property: every selected topic appears proportionally; no repeats inside the exclusion window | Holds for random seeds | P |
| TC-CHK-03 | Timer runs out while offline | Autosaved answers submitted at expiry; late edits refused | F |
| TC-CHK-04 | Reload mid-exam | Resumes same questions, same remaining time | E |
| TC-CHK-05 | Submit twice / from two tabs | One result | A |
| TC-CHK-06 | Question edited after exam started | Exam uses the snapshot | A |
| TC-CHK-07 | Report | Per-topic scores, weak topics created as review boosts, history list | A |
| TC-CHK-08 | Pass mark boundary (79.9 vs 80) | Correct outcome, rounding documented | U |

### 6.5 Research agent
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-RSH-01 | Search provider returns 0 results | Run ends `no_results` with advice; no charge beyond search | A |
| TC-RSH-02 | Provider 429/5xx/timeouts | Backoff, then `partial` or `failed` with reason; retry works | F |
| TC-RSH-03 | Quota exhausted | Run refuses early; UI explains | A |
| TC-RSH-04 | Page blocked by robots/paywall/login | Skipped with reason; counted | A |
| TC-RSH-05 | Page with hidden instructions ("ignore previous...", exfiltration URL) | Treated as data; no tool/URL followed; finding flagged | L |
| TC-RSH-06 | Redirect to private IP or blocked domain | Refused (SSRF suite) | A |
| TC-RSH-07 | Budget (searches, pages, tokens, seconds) reached | Stops cleanly; partial results kept; cost shown | A |
| TC-RSH-08 | Same job researched twice | Idempotent per version; second run adds only new | A |
| TC-RSH-09 | Worker killed mid-run | Task resumes or fails visibly; no duplicate findings | F |
| TC-RSH-10 | Findings contradict each other | Shown side by side with sources; none auto-approved | A |
| TC-RSH-11 | Non-English or very long page | Truncated with marker; language noted | U |
| TC-RSH-12 | Approve finding edits the question text | Edited text re-checked against quote rules | A |

### 6.6 Existing features that must keep passing
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-RAG-01 | Retrieval eval set | recall@5, MRR, abstain at or above `baseline.json` | L |
| TC-RAG-02 | Empty corpus; deleted file; changed model | Clear states; no stale chunks; no mixed dimensions | A |
| TC-MCP-01 | Tool list has no send/delete/settings verbs | Holds | U |
| TC-MCP-02 | Write tool without confirm | Preview only | A |
| TC-MCP-03 | Tool output containing instructions | Returned as data; never executed | U |
| TC-VER-01 | Fabricated quote; wrong URL; shape mismatch | Rejected | A |
| TC-OUT-01 | Approve with flags, suspicious company, daily cap, second message per role | Each guard blocks | A |
| TC-DIS-01 | Board re-read; NUL char; oversize link; blocked redirect | No duplicates; no crash; refused | A |
| TC-TSK-01 | Retry/backoff/watchdog/idempotent key | As documented | A |
| TC-BKP-01 | Backup then restore into new DB; wrong key; same name | Counts equal; refused | A |
| TC-PRC-01 | Infinite loop, network call, huge output in each language | Stopped; blocked; capped | E |

### 6.7 UI, design system, accessibility
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-UI-01 | Theme: first visit, system dark, toggle, reload | Correct theme, no flash, persisted | E |
| TC-UI-02 | Every token pair | Contrast >= AA (script) | U |
| TC-UI-03 | Every route in light and dark | No serious axe violations | E |
| TC-UI-04 | Keyboard: tab order, focus ring visible, dialogs trap and restore focus, Esc closes | Pass | E |
| TC-UI-05 | 375 px width | No horizontal scroll; actions reachable | E |
| TC-UI-06 | Reduced motion | No non-essential animation | E |
| TC-UI-07 | Slow API (3 s) | Skeletons, then data; no layout jump | E |
| TC-UI-08 | API down | Banner; read-only cached data where present; retry | E |
| TC-UI-09 | 10k-row table | Virtualised; scroll smooth | E |
| TC-UI-10 | Command palette: open, search, run, close | Works with keyboard | E |
| TC-UI-11 | Optimistic update fails | Rolled back with toast naming the cause | E |

### 6.8 Architecture explorer
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-EXP-01 | New backend module without a diagram node | Drift test fails | U |
| TC-EXP-02 | New table without ERD entry | Drift test fails | U |
| TC-EXP-03 | Every flow step has text and a linked test that exists | Link check passes | U |
| TC-EXP-04 | Keyboard walk-through of a diagram | All nodes reachable; descriptions announced | E |
| TC-EXP-05 | Live status when DB is down | Shows red with reason, page itself stays up | F |
| TC-EXP-06 | Try-it widgets with hostile input | Handled; rate limited | A |

### 6.9 Data, scale, ops
| ID | Case | Expected | Lv |
|---|---|---|---|
| TC-OPS-01 | Fresh DB to head; previous release to head; head to base | All succeed | A |
| TC-OPS-02 | Pool exhausted / statement timeout | Request fails fast with 503; recovers | F |
| TC-OPS-03 | Retention job | Old rows pruned; recent kept | A |
| TC-OPS-04 | Export then import into empty account | Equal data | A |
| TC-OPS-05 | Two users: every new table isolated | `other_api` tests | A |
| TC-OPS-06 | Container start order; migration lock; restart on crash | Healthy | F |
| TC-OPS-07 | Clock skew between API and DB | Tasks and sessions still behave | F |

## 7. Failure drills (automated, T11); behaviour is specified in `05-system-review.md` section 5
Drop DB connection, slow DB, pool exhaustion, LLM 429/500/timeout/garbage JSON/refusal, embedding model missing, search outage, fetch timeouts, worker crash mid-task, duplicate task delivery, disk full during backup, wrong backup key, migration failure, expired session, double submit, huge payload, hostile strings. Each drill asserts: no data corruption, user-visible message, task state, retry path, and an audit/log line.

## 8. Reporting
CI publishes: test counts, coverage on rule modules, eval table, axe report, visual diffs, agent reports, requirement coverage (T19). A failing eval threshold blocks merge; agent findings do not block but must be triaged within the milestone.

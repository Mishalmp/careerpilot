# 07: Task breakdown (the work list)

Legend: [x] done, [~] partly done (details in STATUS.md), [ ] not started. How to use: take the first unchecked task whose **Deps** are all checked. Do exactly what it says; run its **Done when** check; tick the box and write the commit id after it. If a task is bigger than its size, split it here first. Sizes: **S** up to 1 hour, **M** up to 3 hours, **L** up to 6 hours (hours of focused work, estimates not measurements). Owner tasks are marked **(owner)**.

ID prefixes: Q decisions, X process and tooling, E live-AI enablement and evals, D design system, P pages, B backend platform, L learning platform, R research agent, V architecture explorer, H system hardening, T testing, K containers, W writing and teaching content.
Requirement ids (REQ-nn) are defined in `01-requirements.md`; spec details in `09-product-spec.md`; test cases in `10-test-strategy.md`.

## Milestones and release slices
| Milestone | Contains | Result the owner can see | Rough effort |
|---|---|---|---|
| M0 Decide and baseline | Q, X, E01-E02 | Decisions approved, live AI check done | 6-10 h |
| M1 Design foundation | D01-D22 | `/dev/ui` shows the whole design system in light and dark | 25-35 h |
| M2 New shell and core pages | P01-P07, P14-P17, B01, B02, B15 | The app looks like a SaaS product | 35-50 h |
| M3 Platform prerequisites | B03-B14, H06-H09, T01-T04 | Long actions run as tasks with progress; E2E tests exist | 30-45 h |
| M4 Learning backend | L01-L25, E03-E07 | Questions, quizzes, reviews, checkpoints work through the API | 40-60 h |
| M5 Research agent | R01-R15 | Adding a job finds topics and questions; inbox to approve | 35-50 h |
| M6 Learning frontend | P08-P13, plus Learn screens in section L-UI | You study, practise and take checkpoints in the app | 35-50 h |
| M7 Architecture explorer | V01-V18, W01-W04 | `/architecture` shows interactive diagrams, flows, live status | 35-50 h |
| M8 Trust and hardening | H01-H26, T05-T20 | Chaos drills, AI QA agents, load tests, a11y all pass | 45-70 h |
| M9 Containers | K01-K10 | One command starts everything | 12-20 h |
**Release slices** (ship in this order; each is usable alone): A "Looks right" = M0+M1+M2. B "Learns" = M3+M4+M5+M6. C "Explains itself" = M7. D "Trustworthy" = M8+M9. Total is a multi-month programme at 2 hours a day; do A first because the UI is the owner's top complaint.

## Standard page checklist (used by every P task)
**1 (layout)**: A skeleton and layout from the new shell; B all states (loading skeleton, empty with a call to action, error with retry, partial); C responsive at 375, 768, 1280 px; D copy written (plain, sentence case, verbs consistent).
**2 (behaviour)**: E data hooks and optimistic updates with rollback toast; F keyboard path and focus order; G a11y (labels, roles, contrast in both themes, reduced motion); H component tests; I one E2E test (T02/T03); J screenshot added to visual suite (T05).

## Q: decisions and inputs
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [x] | Q01 | **(owner)** Answer intake questions 1-15 in `08` section 4 (or say "default") | none | S | Answered 2026-11-06; recorded in `01` section 4a |
| [x] | Q02 | **(owner)** Approve or change decisions D1-D10 | Q01 | S | Resolved 2026-11-06 in `01` section 4a (owner said "your choice"/defaults) |
| [ ] | Q03 | **(owner)** Send 2-3 screenshots of apps you like (optional) | none | S | Files in `docs/phase-7/assets/references/` |
| [ ] | Q04 | **(owner)** Put `ANTHROPIC_API_KEY` in `.env`, state a daily budget | none | S | `llm-check` prints OK |
| [ ] | Q05 | Write ADR 0012 design system, 0013 search provider, 0014 long operations, 0015 containers (from approved decisions) | Q02 | M | Four ADRs committed |

## X: process and tooling
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [x] | X01 | Write the Phase 7 plan documents | none | L | `docs/phase-7/` exists |
| [ ] | X02 | Add root `scripts/dev.py` (check, test, up, down) so Windows needs no Makefile | none | M | `python scripts/dev.py check` runs all gates |
| [ ] | X03 | Skill `careerpilot-dev`: lifecycle, gates, rules, how to resume | X02 | M | Skill loads; lists gates |
| [ ] | X04 | Skill `ui-review`: design-system checklist from `02` | D18 | M | Skill reviews a screenshot against tokens |
| [ ] | X05 | Stop hook: run ruff, pyright, import contracts, changed-file tests before a session ends | X02 | M | Hook blocks a deliberate lint error |
| [ ] | X06 | Commit template with task id and "unverified:" line; STATUS.md reminder | none | S | `git commit` shows the template |
| [ ] | X07 | Pre-commit: secrets scan (gitleaks or detect-secrets) and control-character scan | none | S | A fake key and a NUL byte are rejected |
| [ ] | X08 | Read, then install, Anthropic skills `frontend-design`, `webapp-testing`, `mcp-builder` into `.claude/skills/` with licence files | none | M | Files reviewed; listed in STATUS.md |
| [ ] | X09 | **(owner)** Create a GitHub repository; push; enable Actions | none | S | CI runs on push |
| [ ] | X10 | Make CI green on GitHub (fix what only CI reveals: tools, paths, fonts, Postgres client) | X09 | M | All CI jobs green |
| [ ] | X11 | Branch protection and PR template (what changed, tests, unverified, docs) | X10 | S | Template appears |

## E: live AI enablement and evaluations
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | E01 | Run `llm-check` with a real key; record model id acceptance, `effort` parameter, latency, tokens in ADR 0016 | Q04 | S | ADR 0016 committed; failure causes noted if any |
| [ ] | E02 | Live smoke script: each prompt (ask-notes, company-pages, jd-reading, outreach-draft, intel-extract, mock-question, mock-evaluate) on 3 inputs; prints pass/fail | E01 | M | Report saved in `evals/results/` |
| [ ] | E03 | Golden eval sets in `content/eval/llm/<prompt>.yaml`: 20+ cases each, including empty, huge, injection, non-English, contradictory | none | L | Files validated by a schema test |
| [ ] | E04 | CLI `careerpilot eval-llm --prompt X --mode fake or live`; scores table; JSON result file | E03 | M | Fake mode passes thresholds in tests |
| [ ] | E05 | LLM-as-judge grader (different model) with rubric files for subjective prompts | E04, E01 | M | Judge agrees with 10 hand-labelled cases at the stated rate |
| [ ] | E06 | CI: fake-mode evals gate merges; manual workflow for live evals | E04, X10 | S | Failing threshold fails CI |
| [ ] | E07 | Rule: changing a prompt needs a new version file and an eval result in the commit | E04 | S | Script rejects an edited used prompt |
| [ ] | E08 | Price table in settings (per model, dated) and USD cost columns in `llm_calls` reports | none | M | Cost per purpose per day shown |
| [ ] | E09 | Replace the token cap with a USD cap (daily, per run) keeping the token cap as backstop | E08 | M | Test: cap blocks at the dollar limit |
| [ ] | E10 | Evaluate prompt caching and a cheaper model for extraction using E04 scores | E01, E04 | M | Table of cost vs quality in an ADR |
| [ ] | E11 | Provider resilience: timeout, retry with jitter on 429/5xx, circuit breaker, clear user messages | none | M | Tests with mock transport for 429, 500, timeout, malformed |
| [ ] | E12 | Streaming (SSE) for Ask and Mock answers | B05, E11 | M | Tokens appear progressively; cancel works |

## D: design system (details in `02-design-system.md`)
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [x] | D01 | Verify Radix Blue and Slate step values (light/dark) from radix-ui.com/colors; fix the final token list | none | S | `tokens.css` values match source |
| [x] | D02 | Add dependencies (clsx, tailwind-merge, class-variance-authority, lucide-react, next-themes, sonner, cmdk, needed Radix primitives) with a reason and removal path each | Q02 | S | ADR 0012 lists them; build passes |
| [x] | D03 | `components.json`, `lib/utils.ts` (`cn`), folder `components/ui/` without breaking `components/ui.ts` | D02 | S | Existing pages still render |
| [x] | D04 | Global CSS: semantic tokens light and dark, `@theme inline` mapping, radius, shadow, spacing, motion tokens | D01 | M | `/dev/ui` shows both themes |
| [x] | D05 | Theme provider (class strategy, system default, no flash), `color-scheme`, `theme-color`; verify CSP allows the init script | D04 | M | No flash on reload in both themes; CSP test passes |
| [x] | D06 | Self-host fonts (Inter variable, JetBrains Mono) with `next/font/local` | none | S | `next build` works offline |
| [~] | D07 | Primitives: Button (variants, sizes, loading), IconButton, Input, Textarea, Select, Checkbox, Radio, Switch, Label, Field (help, error) | D04 | L | Each has component tests and keyboard test |
| [~] | D08 | Surfaces: Card, Separator, Badge, Avatar, Skeleton, Tooltip, Popover, Dialog, Sheet, DropdownMenu, Tabs | D07 | L | Focus trap and escape tested |
| [ ] | D09 | Data display: Table, DataTable helper, Pagination, EmptyState, ErrorState, Stat, Progress, Toast | D08 | L | Table sorts, filters, keyboard rows |
| [ ] | D10 | Feedback conventions: skeletons, optimistic update with rollback toast, field errors mapped from problem+json | D09 | M | One demo form fails and recovers |
| [ ] | D11 | Command palette (cmdk) and shortcut registry (`g j`, `g t`, `?` help) | D08 | M | Palette opens with Ctrl/Cmd+K; navigates |
| [~] | D12 | Logo mark and wordmark final SVGs (light, dark), favicons (svg, ico, 180 apple), social image | D01 | M | Browser tab shows the mark in both themes |
| [~] | D13 | App shell: collapsible sidebar with groups and counts, top bar (breadcrumbs, search, theme, user menu), mobile drawer, PageHeader | D07, D08, D12 | L | Works at 375/768/1280; keyboard complete |
| [~] | D14 | One icon map (`icons.ts`) from Lucide for nav, entities, statuses | D02 | S | No ad-hoc icon imports (lint rule) |
| [ ] | D15 | Application status colours as semantic tokens with legend | D04 | S | Contrast table passes |
| [ ] | D16 | Chart primitives (bar, sparkline, funnel) using chart tokens, with aria text | D04 | M | Screen-reader text describes data |
| [x] | D17 | Motion tokens and `prefers-reduced-motion` handling | D04 | S | Animations off when reduced |
| [~] | D18 | Dev-only `/dev/ui` gallery of every component and state, theme switch | D07-D10 | M | Gallery renders; excluded from production build |
| [~] | D19 | Contrast script (WCAG ratio and APCA) for all token pairs; axe on `/dev/ui` in both themes | D18 | M | CI fails if a pair drops below AA |
| [ ] | D20 | Visual regression of `/dev/ui` (light, dark) | D18, T01 | M | Baselines committed; diff fails |
| [ ] | D21 | **(owner)** Review `/dev/ui` in both themes; list changes | D18 | S | Change list recorded |
| [ ] | D22 | `docs/design/usage.md`: which component for what, do and do not | D21 | S | Linked from README |
| [~] | D23 | Density setting (comfortable / compact) as tokens (row height, padding, font size) with a switch in Settings and the command palette (REQ-31) | D04 | M | Gallery shows both densities in both themes |

## P: page redesigns (each row = two tasks: 1 layout, 2 behaviour; see the standard checklist)
| 1 | 2 | ID | Page and what is specific | Deps |
|---|---|---|---|---|
| [ ] | [ ] | P01 | Login and first-run checklist (create user, add first job, key set, notes indexed) | D13 |
| [ ] | [ ] | P02 | Today: greeting, due follow-ups, reviews due, research inbox count, today's plan, digest, quick actions | D13, B01 |
| [ ] | [ ] | P03 | Jobs list: dense table, filter bar, saved views, bulk status change, keyboard row navigation | D09 |
| [ ] | [ ] | P04 | Jobs board: accessible drag and drop (dnd-kit) with keyboard alternative; note dialog for skipped stages | D08 |
| [ ] | [ ] | P05 | Job detail with tabs: Overview, Description, Company check, Fit, Interview intel, Outreach, Timeline, Contacts | D08 |
| [ ] | [ ] | P06 | Add job: dialog, quick add from pasted text or URL (parse by code, optional AI) | D08, B04 |
| [ ] | [ ] | P07 | Discover: sources, inbox with bulk actions, digest card | D09 |
| [ ] | [ ] | P09 | Practice: problem list with filters, split workspace (statement, editor, results), timer | D08 |
| [ ] | [ ] | P10 | Ask: conversation view, citations panel, "not in notes" state | D08, E12 |
| [ ] | [ ] | P11 | Mock interviews: start, chat session, summary | D08 |
| [ ] | [ ] | P12 | Insights: charts redesign with chart tokens | D16 |
| [ ] | [ ] | P13 | Offers and Stories | D09 |
| [ ] | [ ] | P14 | Tasks and System status | D09, B01 |
| [ ] | [ ] | P15 | Settings: profile, AI (key present, budget, models), search provider, backups, appearance, data export, danger zone | B03, B19 |
| [ ] | [ ] | P16 | Global states: 404, error boundary, API down banner, session expired | D10 |
| [ ] | [ ] | P17 | Responsive and touch pass over every page | all P |
(P08 Learn is in section L-UI below.)

## B: backend platform prerequisites
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | B01 | `GET /system/status`: API, DB, migration revision, worker heartbeat, queue depth, last runs, LLM configured, embedder loaded, backup age, disk | none | M | Test covers each field and failure value |
| [ ] | B02 | Worker heartbeat row updated each tick; watchdog uses it instead of only `started_at` | B01 | M | Killed worker detected within 2 ticks (test) |
| [ ] | B03 | Profile and settings in the database (skills, levels, regions, pay) with API; import from `profile.yaml` once | none | L | UI edits persist; scoring reads DB |
| [ ] | B04 | Long operations as tasks (verify, score with AI, outreach generate, intel extract, research) returning 202 and a task id | B05 | L | Web request returns fast; result appears on completion |
| [ ] | B05 | Task progress events (JSONB log) and SSE endpoint with polling fallback and auth | B02 | L | Client shows live steps; reconnect resumes |
| [ ] | B06 | Audit log for every write through services (who, what, before/after summary); viewer API | none | M | Test: each POST/PATCH/DELETE writes a row |
| [ ] | B07 | Rate limits for costly endpoints (per minute, per user) with 429 and retry-after | none | M | Burst test returns 429 |
| [ ] | B08 | Persist login throttle in DB; per IP and per email; lockout window setting | none | M | Survives restart (test) |
| [ ] | B09 | Session list, revoke, sign out everywhere, change password | none | M | Revoked cookie fails (test) |
| [ ] | B10 | Retention jobs: `llm_calls`, succeeded `tasks`, `digests`, `audit_events`; settings | B01 | M | Old rows pruned in test with clock injection |
| [ ] | B11 | Seed 50k jobs and 500k chunks; EXPLAIN key queries; add missing indexes; perf thresholds | T16 | L | p95 targets in `10` met |
| [ ] | B12 | Every list endpoint paginated with a limit; contract test over OpenAPI | none | M | Test fails for an unpaginated list |
| [ ] | B13 | `Idempotency-Key` on create endpoints used by imports, MCP and tasks | none | M | Replay returns same result |
| [ ] | B14 | Typed error codes (enum) in problem+json and in the OpenAPI schema | none | S | Frontend maps codes to messages |
| [ ] | B15 | Startup configuration report: all invalid settings listed together; shown in status | none | S | Bad config prints one clear page |
| [ ] | B16 | Request id propagated into task logs and audit rows | B06 | S | Same id visible end to end |
| [ ] | B17 | Metrics (Prometheus text) for requests, tasks, LLM cost | B01 | S | Endpoint scraped in test |
| [ ] | B18 | Undo window for deletes of jobs and stories (soft delete 30 days) | none | M | Restore works; purge job removes |
| [ ] | B19 | Full data export (JSON zip) and import into an empty account | none | L | Round trip equals original (test) |
| [ ] | B20 | Multi-user readiness review: per-user settings and keys documented, tests for isolation of every new table | none | M | Checklist in `05` completed |
| [ ] | B21 | Invite-only sign-up (admin creates an invite link/code), per-user USD budget on the shared server key, admin view of usage (REQ-29) | B03, E09 | L | Invited user signs up; cannot exceed own cap; cross-user tests |

## L: learning platform (spec: `03-learning-platform.md`)
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | L01 | ADR 0017 learning model; freeze spec | Q02 | M | ADR committed |
| [ ] | L02 | Migration + models: `tracks`, `topics` (from `prep_topics`), `topic_edges` (prerequisites), tags | L01 | M | Drift test green; up/down tested |
| [ ] | L03 | Migration + models: `questions`, `question_options`, `question_sources` | L02 | M | Constraints per type enforced by CHECKs |
| [ ] | L04 | Migration + models: `attempts`, `review_cards` (FSRS state) | L03 | M | One card per (user, question) unique |
| [ ] | L05 | Migration + models: `checkpoints`, `checkpoint_items`, `checkpoint_attempts` | L03 | M | Snapshot of questions stored per attempt |
| [ ] | L06 | Migration + models: `research_runs`, `research_findings` | L03 | M | Status enums and budgets columns |
| [ ] | L07 | Idempotent data migration of existing topics, study sessions and guide questions into the new model; old endpoints keep working | L02-L04 | L | Row counts equal; reversible |
| [ ] | L08 | FSRS scheduler service (py-fsrs pinned) with rating-to-interval tests on known sequences | L04 | M | Matches reference intervals |
| [ ] | L09 | Rating rules from answers: correctness, confidence, time -> Again/Hard/Good/Easy (pure) | L08 | S | Table-driven tests |
| [ ] | L10 | Question CRUD API with per-type validation (mcq single/multi, short answer, practical, explain, scenario) | L03 | L | Invalid shapes rejected; owner scoping tests |
| [ ] | L11 | Grounding validator: source quote must verify; correct option must be supported by quote; else reject or mark `unverified` | L10 | M | Fabricated question rejected |
| [ ] | L12 | Dedupe: normalised hash plus embedding similarity; merge suggestion | L10 | M | Near-duplicates detected at threshold |
| [ ] | L13 | MCQ generator workflow: generate, blind answer by second call, grounding check, store `draft` | L11, E04 | L | Eval: wrong-key rate under target |
| [ ] | L14 | Short-answer grader: rubric criteria, deterministic pre-checks, LLM grade, per-criterion feedback | E05, L10 | L | Agrees with hand labels |
| [ ] | L15 | Practical questions: link to practice problems; "create a problem" validated in the browser runner (reference solution must pass its tests) before saving | L10 | L | Invalid LLM problem cannot be saved |
| [ ] | L16 | Review queue: due cards, daily cap, interleave topics, new-card limit | L08 | M | Order and caps tested |
| [ ] | L17 | Quiz sessions: start by topic/mixed/weak; answer with idempotency token; results | L10 | M | Double submit safe |
| [ ] | L18 | Checkpoint builder (pure): coverage by topic weight, difficulty mix, type mix, exclusion window, seeds for reproducibility | L10 | L | Property tests: coverage and no repeats |
| [ ] | L19 | Checkpoint API: create, start (timer), autosave, submit once, report with per-topic result and weak topics feeding reviews | L18, L05 | L | Expiry and double submit tested |
| [ ] | L20 | Roadmap service: editable plan (weeks, days) from topics and job gaps (job skills minus mastered topics) | L02 | L | Gap list matches fixtures |
| [ ] | L21 | Mastery and progress analytics (retrievability average per topic, coverage, streak, minutes) | L08 | M | Values match hand calculation |
| [ ] | L22 | Due counts for Today and sidebar badges | L16 | S | Counts equal queue |
| [ ] | L23 | MCP read tools: due reviews, topic mastery, checkpoint results | L16, H17 | M | In-memory MCP tests |
| [ ] | L24 | Import existing guide questions as source `guide` questions | L10 | M | Idempotent import |
| [ ] | L25 | Learning event log (view, answer, hint, skip) for debugging and analytics | L04 | S | Events written in tests |

## L-UI: learning screens (P08)
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | LU01 | Learn home: today's plan, reviews due, weak topics, research inbox, recent checkpoint | L16, L21, D13 | L | Page checklist 1-2 |
| [ ] | LU02 | Roadmap editor: add/remove/reorder topics, set target date, see gaps for chosen jobs | L20 | L | Edits persist |
| [ ] | LU03 | Topic page: summary, sources, questions list, mastery, notes, add question | L10 | L | |
| [ ] | LU04 | Question card components: MCQ single/multi, short answer, practical (embedded editor), explain, scenario | D08, L10 | L | Keyboard answerable |
| [ ] | LU05 | Quiz runner: progress bar, confidence selector, instant feedback with explanation and source | LU04, L17 | L | Resumes after reload |
| [ ] | LU06 | Review session UI (spaced repetition) with rating feedback and next-due preview | LU04, L16 | M | |
| [ ] | LU07 | Research inbox UI: grouped findings, source and quote, approve/edit/reject, bulk approve | R09 | L | |
| [ ] | LU08 | Add knowledge manually: paste text or link, convert to topics and questions (with AI optional) | R05, L13 | M | |
| [ ] | LU09 | Checkpoint setup, exam screen (timer, flag, navigator), report with topic breakdown and "what to review" | L19 | L | Timer survives reload |
| [ ] | LU10 | Question bank browser: filter by topic, type, status, source; bulk edit | L10 | M | |
| [ ] | LU11 | Learning insights panel (mastery map, streak, time) | L21, D16 | M | |

## R: research agent (spec in `03`, section 3)
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | R01 | `SearchProvider` interface, Fake and Brave implementations, quota and cost tracking | Q02 | M | Provider swap by setting |
| [ ] | R02 | Query planner from job title, company and JD skills (templates first; optional model); blocked domains removed | R01 | M | Snapshot tests |
| [ ] | R03 | Fetch pipeline additions: robots.txt respect, per-host rate limit, page cache with TTL | none | L | Blocked by robots (test); cache hit tested |
| [ ] | R04 | Main-content extraction to cut tokens | R03 | M | Fixture pages reduced with key facts kept |
| [ ] | R05 | Parallel extraction workers with bounded concurrency; quote verification; findings stored | R04, E03 | L | Fabricated quote rejected |
| [ ] | R06 | Evaluator step: relevance and specificity score per finding; code sets thresholds | R05 | M | Low-value findings flagged |
| [ ] | R07 | Budgets per run (searches, pages, tokens, seconds) enforced and reported | R05 | M | Run stops at limits (test) |
| [ ] | R08 | Run orchestration as a task with progress events; idempotent per job and version; resumable | B04, B05 | M | Kill and resume test |
| [ ] | R09 | Inbox API: list grouped, approve, edit, reject, bulk approve; approval creates topics and questions | R06, L10 | M | Owner scoping tests |
| [ ] | R10 | Triggers: ask when a job is added; manual button; stale refresh after 30 days | R08 | S | Opt-in respected |
| [ ] | R11 | Provenance shown for every item ("why am I seeing this") | R09 | S | Source, date, reliability in API |
| [ ] | R12 | Failure matrix implemented (provider down, quota, zero results, paywall, injection, budget) with user messages | R08 | M | One test per row of the matrix in `05` |
| [ ] | R13 | Adversarial page corpus for prompt injection; tests that nothing leaks or acts | R05 | M | All corpus pages neutralised |
| [ ] | R14 | Content rules: store link, short quote and paraphrase only; blocked sites list kept | R05 | S | Test: long quote truncated |
| [ ] | R15 | Research quality eval: 10 sample roles with expected topics; recall metric | R05, E04 | L | Baseline recorded |
| [ ] | R16 | CV-driven profile: paste/upload CV text, extract skills, years, role titles and seniority (code first, optional model), owner edits, saved to the profile (REQ-28); role titles feed R02 queries and the roadmap | B03, E04 | L | Fixture CVs give expected skills and titles; no hard-coded role list |
| [ ] | R17 | Spike: prove SearXNG JSON search works from the fetcher with limiter settings; record the working `settings.yml`/`limiter.toml`; decide default provider | R01 | M | Spike note in ADR 0013; 20 queries return results |

## V: architecture explorer (spec: `04-architecture-explorer.md`)
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | V01 | Content schema in `content/architecture/` (nodes, edges, flows, concepts) with loader and validation | none | M | Invalid file fails test |
| [ ] | V02 | API and CLI `careerpilot export-architecture`: architecture graph, concept index, ERD from SQLAlchemy metadata, routes, tasks, prompts, MCP tools written to `content/architecture/generated/` | V01 | M | Owner-independent; tests; generated files equal a fresh export |
| [ ] | V03 | Drift tests: modules, routers, tables, ADRs vs the content | V02 | M | Adding a module without a node fails |
| [ ] | V04 | `/architecture` shell with tabs | D13 | S | Route renders |
| [ ] | V05 | React Flow wrapper: pan, zoom, minimap, node panel, keyboard access, theming, reduced motion | D04, V04 | L | Keyboard can reach every node |
| [ ] | V06 | Diagram: system context | V05 | M | Matches `04` |
| [ ] | V07 | Diagram: backend modules and allowed dependencies from import-linter contracts | V05 | M | Generated from contracts |
| [ ] | V08 | Flow player (play, step, back) with flows: login and CSRF; add job; ask notes; company check; research run; discovery and queue; backup and restore; mock turn | V05 | L | Each flow has step text and linked test |
| [ ] | V09 | ERD view with module filter and live row counts | V02, V05 | M | |
| [ ] | V10 | Concept pages (What, Why, In this app, Failure modes, Try it, Proving test) | W01 | L | 14 pages render |
| [ ] | V11 | Try-it widgets: chunking, rank fusion, SSRF checker, quote verifier, backoff calculator, FSRS simulator | V10 | L | Each calls real code via API |
| [ ] | V12 | Live status panel (from B01) | B01, V04 | M | Shows real values |
| [ ] | V13 | Failure drills page: scenario, what happens, proving test, how to simulate in dev | W02, T11 | M | Each drill links a passing test |
| [ ] | V14 | ADR viewer and decision timeline | V01 | M | All ADRs listed |
| [ ] | V15 | Search across architecture content in the command palette | D11, V10 | S | |
| [ ] | V16 | Export diagrams as SVG and PNG | V05 | S | |
| [ ] | V17 | Text alternative for every diagram; keyboard narrated walk-through | V05 | M | axe clean |
| [ ] | V18 | **(owner)** Review the explorer; list changes | V06-V14 | S | |

## H: system hardening and redesigns (rationale in `05-system-review.md`)
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | H01 | Option to run the worker as its own process/container; API stays usable if worker is down | B02 | M | Two-process test |
| [ ] | H02 | Queue: per-kind concurrency, priorities, per-provider rate limits | none | M | Tests |
| [ ] | H03 | Queue: classify errors retryable vs permanent; permanent fails at once | none | S | Test |
| [ ] | H04 | Queue: cancel a running or queued task | B05 | M | Cancel mid-run test |
| [ ] | H05 | Queue: LISTEN/NOTIFY wake-ups with polling fallback | none | M | Latency test |
| [ ] | H06 | Idempotency audit of every POST (table in `05`) and fixes | B13 | M | Replay tests |
| [ ] | H07 | Transaction audit: `call_llm` commits inside service flows; move usage recording to its own session | none | M | No partial state on LLM failure (test) |
| [ ] | H08 | DB: statement and lock timeouts, pool size, pool-exhaustion behaviour | none | M | Test with tiny pool |
| [ ] | H09 | DB: migration checks (fresh up, previous release up, down, enum-constraint helper that prevents the 0012 mistake) | none | M | CI job |
| [ ] | H10 | DB: weekly restore drill into a temporary database with row-count check | none | M | Task and test |
| [ ] | H11 | DB: archive/partition plan for `llm_calls`, `tasks`, `audit_events` | B10 | S | ADR |
| [ ] | H12 | RAG: `embedding_version` and re-embed task; model change never mixes dimensions | none | M | Test with two dims |
| [ ] | H13 | RAG: reranker and contextual-retrieval A/B on the eval set | L24 | L | Table in an ADR |
| [ ] | H14 | RAG: eval set to 100 questions with adversarial cases and a faithfulness check | none | L | Baseline file |
| [ ] | H15 | RAG: stale chunk and deleted file tests | none | S | |
| [ ] | H16 | RAG: pgvector iterative scan with owner filter at larger scale | B11 | S | Recall check at 500k |
| [ ] | H17 | MCP: align with the current spec version (2026-07-28 found 2026-11-06); verify SDK support; tool annotations audit | none | M | Compatibility note in ADR |
| [ ] | H18 | MCP: tool-poisoning and confirm-flow tests; audit rows | none | M | |
| [ ] | H19 | LLM: fallbacks (cheaper model), budget alerts in UI | E09 | M | |
| [ ] | H20 | Security headers review with new libraries (CSP, Permissions-Policy), markdown sanitiser tests | D05 | M | Header tests |
| [ ] | H21 | SSRF re-test: IPv6, redirects, DNS tricks, proxies; robots interplay | R03 | M | Suite extended |
| [ ] | H22 | Threat model refresh for research agent and learning content (XSS, injection, data exfiltration) | R05 | M | Updated section in plan |
| [ ] | H23 | Frontend performance: bundle analysis, lazy-load Pyodide, CodeMirror, React Flow; virtualised long lists | D13 | M | Budgets in CI |
| [ ] | H24 | Observability: log viewer in System page; error counts | B16 | M | |
| [ ] | H25 | Secrets doc: `.env` permissions, BitLocker, key rotation | none | S | Runbook |
| [ ] | H26 | Disaster-recovery runbook rehearsed once | H10 | S | Dated log |

## T: testing (strategy in `10-test-strategy.md`)
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | T01 | Playwright setup: browsers, config, fixtures (seeded DB, login helper, API server on test DB, per-worker isolation) | none | L | `npm run e2e` runs one test |
| [ ] | T02 | E2E smoke: login, add job, move status, run a problem, ask (fake model), view Insights | T01 | M | Green on CI |
| [ ] | T03 | E2E per page, added with each P task | T02 | L | Listed in `10` |
| [ ] | T04 | axe sweep of every route in both themes | T01, D19 | M | Zero serious violations |
| [ ] | T05 | Visual regression suite for key pages | T01 | M | Baselines |
| [ ] | T06 | Cross-browser run (Chromium, Firefox, WebKit) | T02 | S | Matrix green |
| [ ] | T07 | API fuzz from OpenAPI (schemathesis) with auth | none | M | No 500s |
| [ ] | T08 | Property tests (hypothesis) for IP classifier, quote normaliser, FSRS, workflow, scoring, checkpoint builder | none | M | |
| [ ] | T09 | Mutation test on rule modules (mutmut) to measure test strength | T08 | M | Score recorded |
| [ ] | T10 | Load tests (k6 or Locust) on key endpoints with seed scale | B11 | M | Thresholds met |
| [ ] | T11 | Failure drills automated: DB drop, slow DB, LLM 429/500/timeout/garbage, search outage, worker crash mid-task, disk full on backup, clock skew | H07 | L | Each drill asserts behaviour in `05` |
| [ ] | T12 | ZAP baseline scan and header tests against the running stack | K03 | M | Report, no high findings |
| [ ] | T13 | **AI QA agent (explorer)**: Claude with browser tools runs missions and writes a report; pilot and measure false positives | T01 | L | Report reviewed by owner |
| [ ] | T14 | **AI QA agent (personas)**: missions in `tests/agent-missions/*.md` for new, power and hostile users | T13 | L | Reports in `reports/` |
| [ ] | T15 | Policy: agents may propose fixes to locators and scripts; humans approve | T13 | S | Documented |
| [ ] | T16 | Data factories and seed scenarios (empty, 1k jobs, 50k jobs, 500 questions) | none | M | Used by B11, T10 |
| [ ] | T17 | Flaky test policy: quarantine list, one retry for E2E only | T02 | S | |
| [ ] | T18 | Coverage gates on rule modules (95%) | none | S | |
| [ ] | T19 | Traceability script: requirement id to tests (`# covers: REQ-12`); fail if a requirement has none | Q02 | M | Report in CI |
| [ ] | T20 | Manual screen-reader pass checklist (NVDA) | D13 | S | Checklist signed |

## K: containers
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | K01 | API Dockerfile: uv multi-stage, non-root, healthcheck, model cache volume | none | M | Image runs `/readyz` |
| [ ] | K02 | Web Dockerfile: standalone output, non-root | D06 | M | Image serves login |
| [ ] | K03 | Compose profiles: `db`, `app` (api, worker, web), `tools` | K01, K02 | M | `docker compose --profile app up` works |
| [ ] | K04 | Env and secret handling, volumes (data, models, backups) | K03 | S | Documented |
| [ ] | K05 | Dev ergonomics in `scripts/dev.py` (up, down, logs, shell) | X02, K03 | M | Windows verified |
| [ ] | K06 | One-shot migration service with lock | K03 | S | Two starts safe |
| [ ] | K07 | Healthchecks, `depends_on` conditions, restart policy | K03 | S | Kill test restarts |
| [ ] | K08 | CI image build and vulnerability scan | K01, X10 | M | Advisory report |
| [ ] | K09 | AWS deployment notes (ECS, RDS, S3 backups) | K03 | S | Doc |
| [ ] | K10 | Optional HTTPS reverse proxy (Caddy) | K03 | S | Doc |

## W: writing and teaching content
| Done | ID | Task | Deps | Size | Done when |
|---|---|---|---|---|---|
| [ ] | W01 | Turn `06-concepts-primer.md` into `content/architecture/concepts/*.md` (14 pages) | V01 | L | Loader validates |
| [ ] | W02 | Failure-mode docs from `05` as drill content | V01 | M | |
| [ ] | W03 | Glossary (terms, one line each, linked) | W01 | S | |
| [ ] | W04 | Code tour: module by module "where to look" | V01 | M | |
| [ ] | W05 | Talking points for interviews about this project, only claims backed by the repo | all | M | Claims audit |
| [ ] | W06 | README, CLAUDE.md, ADR updates at each milestone | milestones | S each | |
| [ ] | W07 | Runbooks: backup/restore, rotate keys, upgrade dependencies, incident | H25 | M | |
| [ ] | W08 | Changelog and release notes | none | S | |
| [ ] | W09 | Portability guide `docs/setup/`: new machine on Windows/macOS/Linux, `.env` creation, running native and with Docker, deploying to a server, zipping backups and restoring on another machine, troubleshooting (REQ-30) | K03 | M | A clean checkout follows it to a running app (tested at least on Windows + one container run) |

## Changes to the plan
(Append dated entries here when the plan changes: what, why.)
- 2026-11-06: plan created.
- 2026-11-06: docs 02-05 written; task ids in them cross-checked against this file; V02 now includes the `export-architecture` command; requirement ids are REQ-nn.

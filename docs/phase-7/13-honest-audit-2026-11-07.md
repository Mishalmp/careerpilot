# 13: Honest audit, 2026-11-07: what was asked, what exists, how far to trust it

Written because the owner asked for "requirement expectation versus what has been done, what needs to be done, how accurate and durable it is, brutally honest". Every statement below says how it was checked. Where something was never run for real, it says so. Re-do this audit before any release.

## 1. The short version
- The **core product works and is well tested in isolation**: tracker, company checks, scoring, outreach drafts (no send), notes search, practice runner, learning with spaced repetition and exams, the daily apply list, account setup, background tasks with history and retry, backups. On 2026-11-07 the full suites passed: 1,141 API tests (1 skipped: the optional model-quality test), 50 web unit tests, 117 browser tests (Chrome), plus lint, strict type checks and 24 import rules.
- Almost everything that talks to the **outside world has never been run for real**: web search, the research agent, Claude calls, GitHub reading, OCR on real scanned CVs, job-page parsing for pay and interviews. They are tested with fakes and generated samples. That is the biggest gap between "tests pass" and "works".
- The **UI is consistent but not yet "styled and interactive" everywhere**: the pages built this phase (Today, Learn, Jobs, Apply, Profile and setup, Activity, Architecture) use one design system and have hover, motion and empty states; about nine older pages only share the controls and headers, not a redesigned layout.
- It is **not production grade yet** for strangers: no password reset by email, no per-user rate limits, no CSP on pages, CV text stored unencrypted, CI never run, no alerts, no multi-user. It is fine for the owner on one machine.

## 2. Requirements versus reality
Legend: **Done** = built and tested; **Partly** = built with stated gaps; **No** = not built. "Verified how" is the strongest check that exists.

| Requirement | Status | Verified how | What is missing |
|---|---|---|---|
| 01 Blue light and dark theme, switch, no flash | Done | browser tests, contrast script | none known |
| 02 One design system | Partly | components used by new pages; legacy class strings restyled to match | about nine pages still use the legacy strings and their own layouts |
| 03 Logo, favicon, icons | Done | visual check | none |
| 04 Seamless UX, shortcuts, palette, responsive, WCAG 2.2 AA | Partly | axe (serious/critical) on every page in both themes; layout audit at 375, 768, 1280 px; target-size check | no command palette; keyboard shortcuts only in review; never tested with a screen reader or on a real phone |
| 05 Front-end security | Partly | headers set; no secrets in the browser; runner workers have a CSP | no CSP on app pages |
| 06 No predefined roadmap | Partly | Learn starts empty | the Prep area still offers a built-in 45-day plan (optional import) |
| 07, 08 Agentic research with budgets, inbox, verified quotes | Partly | 49+ tests with fake search, web and model; quotes verified by code; resume after a crash tested | **never run against a real search service or Claude**; no reliability score for sources |
| 09 Question types | Partly | MCQ and written (self-rated) | model grading and practical questions in exams not built |
| 10 Practical questions validated | Partly | runner exists | AI-drafted problems not built |
| 11 Spaced repetition | Done | unit and API tests | not compared with a reference scheduler beyond the library's own tests |
| 12 Checkpoint exams | Partly | API and browser tests | multiple choice only |
| 13 Mastery, gaps, roadmap from gaps | No | | not built |
| 14, 15, 17 Explorer, concepts, drift tests | Partly | drift tests fail if code and content diverge | ERD, drills, ADR viewer, try-it widgets, export missing |
| 16 Live status | Partly | status endpoint and tab | no worker heartbeat |
| 18 Written senior review | Done | `05` | its hardening tasks (H-group) are 0 of 26 done |
| 19 Long work never blocks; progress; retry | **Done now** | tests incl. simulated crash and continue; browser tests of history, retry, cancel | backups and board reads simply restart (they are idempotent); no worker heartbeat |
| 20 AI budgets and audit | Partly | token cap per day and per run; every call audited; call log on screen | no dollar budgets, no per-call cap |
| 21 Controlled AI output | Partly | schema validation, quote checks, human approval gates | evals exist only for notes search |
| 22 Scalable path, isolation | Partly | every query scoped by owner, cross-owner tests per resource | stage-3 checklist not done |
| 23 One command containers | Partly | built and run on Windows Docker Desktop | not tried on macOS or Linux |
| 24 to 27 Docs, tasks, AI-driven E2E, education | Partly | docs complete and current | no AI-driven end-to-end testing |
| 28 Dynamic profile from CV | **Done now** | account setup, CV upload (PDF, Word, text), paste, OCR (optional), GitHub reading, scoring from the profile; 120+ tests | OCR checked only on generated pictures; scoring weights still tuned for software roles |
| 29 5 to 10 invited users | No | | no invites, admin screen, per-user caps, password reset |
| 30 Portable setup guide | Partly | guide written, followed on Windows | other systems untested |
| 31 Density and logo variants | Done | browser tests | none |

Task list totals (`07-tasks.md`): 45 done, 39 partly, 132 not started of 216. Groups with nothing started: H (hardening, 26), E (AI evals and budgets, 12), most of B (backend platform) and T (test strategy).

## 3. What was found wrong today and fixed
| Finding | How it was found | Fix |
|---|---|---|
| The CV reader missed many real technologies (CloudWatch, ECR, SQS, KMS, RDS, GitLab, data lake...) | Ran it on the owner's real CV: 29 skills found, plus a list of capitalised technology names that were not in the vocabulary | Added about 50 skills; short acronyms are matched in capitals only; recall on that CV rose from 29 to 39. The comment in `skills.yaml` promised an `exact_case` option that did not exist: it now does |
| OCR glued words together ("SeniorPythonBackend"), losing most skills | Generated a scanned CV and ran the real OCR engine: 1 of 10 skills found | Enlarge the picture 2x before OCR (measured to restore spaces), repair "APl" to "API": 10 of 10 skills, title and years right |
| "Validation failed" was all a user saw when input was rejected | Browser test of a wrong GitHub link | The UI now shows the field and the reason |
| Account setup would have wiped an auto-filled name | Reasoning about the wizard, then a unit test | The form only sends fields you edited |
| The wizard jumped back to step 1 after each save | Browser test | The wizard no longer remounts on save |
| A name in a link top bar failed a screen-reader rule (visible text not in the accessible name) | axe in the browser test | Removed the redundant label |
| The jobs table forced sideways scrolling and clipped the status on phones | Layout audit screenshots | Secondary columns hidden below tablet width |
| The old Tasks page showed bare text, no history, retry did not say where it stopped | Screenshot review | Replaced by Activity (progress bars, per-attempt history, retry, cancel, AI call log) |
| One run of the whole test suite gave false failures | I started a second test run against the same test database | Process lesson: never run two test runs at once (they truncate the same tables). The suite was rerun alone |

## 4. How accurate and durable is it, really
| Area | Evidence | Honest rating |
|---|---|---|
| Status rules, tracker, scoring math | Exhaustive table tests | High for the rules; the *weights* are untested guesses |
| Company verdicts | Rule tests; evidence needs quotes that exist | Medium: depends on a company having a findable website |
| CV skills | One real CV (39 found; unknown misses remain) and generated samples | Medium-low until measured on 10+ CVs of different fields |
| CV roles and years | Rule tests, one real CV | Medium-low |
| OCR | Generated pictures only | Low-medium: works on clean text, never tried on a photo or a two-column CV |
| Pay figures from pages | Hand-written table of 16 formats, quotes shown | Low-medium: formats vary widely; always read the quote |
| Interview sentences from pages | Rule tests | Low-medium: finds sentences about a process, cannot judge them |
| "Same job on another site" | Fake search results | Unknown on real search results |
| Research agent | Fakes | Unknown |
| Learning and exams | API and browser tests | High for mechanics, unknown for content quality (the user supplies content) |
| Background tasks | Tests including crash and continue | High for the queue; durability depends on one Postgres and one process |
| Backups | Encrypted dump made and restored into a new database in a container | Good; copy off the machine is manual |
| Security | Throttle, CSRF, cookie flags, SSRF guard, upload limits, owner scoping tests | Good for one user; not reviewed by anyone else; not for strangers yet |

## 5. What to do next, in this order
1. **Make the first real run** (owner, 30 minutes): start SearXNG, press "Build today's list", upload the real CV, read the cards critically, note every wrong line. This turns the biggest unknown into numbers. (If an Anthropic key is added, run `llm-check` and one research run.)
2. Create the private GitHub repository so CI runs (X09, X10).
3. Do the "urgent" items in `12` Part B (worker heartbeat, per-user rate limits, encrypt CV text, report-only CSP).
4. Measure the CV reader on 10 CVs and the pay parser on 50 real pages; put the numbers here.
5. Redesign the remaining pages with the shared components; add the command palette.
6. Only then start the role-agnostic design (Part A of `12`).

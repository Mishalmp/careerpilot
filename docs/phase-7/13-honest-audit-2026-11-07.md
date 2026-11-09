# 13: Honest audit, 2026-11-07: what was asked, what exists, how far to trust it

Written because the owner asked for "requirement expectation versus what has been done, what needs to be done, how accurate and durable it is, brutally honest". Every statement below says how it was checked. Where something was never run for real, it says so. Re-do this audit before any release.

## 1. The short version
- The **core product works and is well tested in isolation**: tracker, company checks, scoring, outreach drafts (no send), notes search, practice runner, learning with spaced repetition and exams, the daily apply list, account setup, background tasks with history and retry, backups. On 2026-11-07 the full suites passed: 1,141 API tests (1 skipped: the optional model-quality test), 50 web unit tests, 117 browser tests (Chrome), plus lint, strict type checks and 24 import rules.
- Part of what talks to the **outside world has now run for real** (section 6: live search, live job boards, page fetching, pay and interview reading, company checks) and found six real bugs, all fixed. Still never run for real: the research agent, Claude calls, GitHub reading, OCR on a real scan. They are tested with fakes and generated samples.
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

## 6. The first real run (2026-11-07, same day)
What ran for real: a free SearXNG container (live web results), live Greenhouse job boards (Cloudflare 464 listings, Databricks 924), the owner's real CV uploaded as a file, account setup, the daily apply list with real searches and real page fetches, and the company checks against live DNS and websites. A scratch database and a test account were used; the owner's database was not touched, and the scratch data was deleted afterwards.

What worked, measured:
- Discovery read both boards live: 1,388 listings, 521 kept by the title filter. The CV reader found 40 skills, the right two titles and 6 years from the real CV.
- Building a list took about 15 to 30 seconds for 2 jobs, with 5 searches and up to 3 pages per job.
- **Pay**: both jobs had the pay range in the post itself (found by the regex, shown with the quote): correct on both.
- **Interview information**: real, useful sentences ("4 steps: recruiter screen, technical phone screen, hiring manager call...") with their sources, after the fix below.
- **Same job elsewhere**: one real match on another site (skills in common 64%), others correctly labelled "similar role" and "page not opened".
- Sites that forbid automation (LinkedIn) appeared as links only.

What the real run found wrong (all fixed, with tests):
| Finding | Cause | Fix |
|---|---|---|
| "Interview information" was page titles and marketing lines ("Databricks Interview Questions and Answers: 2026 Edition") | Search result titles were mined as sentences; any sentence with "interview" counted | Only snippets and page text are used; a sentence must describe the process (rounds, coding, design, stages...); titles, pipes and sales lines are dropped |
| A two-year-old post (746 days) was on the list | No age rule | New policy setting `max_age_days` (default 120, 0 = any) |
| The company check never ran for discovered companies | Companies found through a job board have no website on file | The employer's own address is taken from the post when it is not a job-board address |
| A real company (Databricks) showed "suspicious, 0 of 8" | A DNS outage on this machine made its website look fake; and the list printed "suspicious" together with "no red flags" | An unresolvable site is only a failed check when other sites do resolve; the list says "unverified" unless something was found against the company. After the fix: 4 of 8 passed |
| A first lookup failed once and then worked ("Could not resolve boards-api.greenhouse.io") | Transient DNS failure | The safe fetcher tries a failed name once more after a second |
| An empty search result gave no explanation | Free search engines behind SearXNG are rate-limited (it reported "too many requests" and a CAPTCHA) | The card now says "A search returned nothing... try again in a few minutes" |

Still not verified after this run:
- Only 2 jobs from one company (Databricks) reached the list; pay and interview accuracy on many companies is unmeasured. Only one job was a "same job elsewhere" match.
- Pay for a Berlin job came from a US pay range of an earlier post: it is labelled "an earlier or similar post", but no one checks that the region matches.
- The research agent, Claude, GitHub reading and OCR on a real scan were not part of this run.
- The free search service is flaky by nature (two engines were rate-limited during the run): expect gaps and rerun later; a paid or keyed provider (Tavily's free tier) is steadier.

## 5. What to do next, in this order
1. **Repeat the real run on more companies** (the first one is in section 6): follow 5 to 10 boards, build several days of lists, read every card critically. For the research agent and Claude, add an Anthropic key and run `llm-check` and one research run.
2. Create the private GitHub repository so CI runs (X09, X10).
3. Do the "urgent" items in `12` Part B (worker heartbeat, per-user rate limits, encrypt CV text, report-only CSP).
4. Measure the CV reader on 10 CVs and the pay parser on 50 real pages; put the numbers here.
5. Redesign the remaining pages with the shared components; add the command palette.
6. Only then start the role-agnostic design (Part A of `12`).

## 7. Second real run and the empty list (2026-11-09)

What the owner saw on Nov 8: an empty Apply list and 19 "Done" tasks with nothing to look at. Cause, found by reading the database: the discovery runs read 456 free-feed jobs, none fitted the single search "India on site or hybrid" (the feeds are almost all remote), so nothing waited; even when something waits, the list is built only from jobs in the tracker, and listings reached the tracker only when accepted by hand; and neither the task history nor the pages said any of this.

Fixes (all tested, then run for real on a scratch copy with the real feeds, 41 checked boards and SearXNG): automatic copy of fitting listings into the tracker, result lines in the history, empty-state explanation, per-board "kept and why not".

Real results, first run: 8,930 listings from 46 sources, 2,933 fitted the searches, 61 copied, 50 listed. **What the real data exposed that tests did not**: (1) the list contained a product manager and "Sales Engineer" jobs, because skills named in a long description outweighed a non-matching title and a plain "Software Engineer" on the CV matched every "X Engineer": auto-add now requires a development-like title (no sales, support, solutions, customer-success words); (2) the "why left out" text said only "fits none of your 4 searches", which explains nothing: it now lists the distinct reasons. After the fixes: 80 copied, 35 listed, 22 of them in India, none with a non-engineering title; a handful of listed titles are still dubious (for example "Manager, Site Reliability Engineer"), because the title rule is deliberately simple.

Still true: nothing from LinkedIn, Indeed, Glassdoor or Naukri is read; India on-site coverage rests on the Indian-hiring companies on the checked list plus pasted links until an Adzuna or Jooble key is added. The Telegram bot was tested only against a fake Bot API.


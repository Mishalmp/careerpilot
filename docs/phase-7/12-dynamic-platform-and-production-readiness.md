# 12: A platform for any role, and what "production grade" still needs

Two parts. Part A is a **design for later** (owner request, 2026-11-07: "make it completely dynamic, irrespective of software developer, whatever their role: interviews, mock and so on"). It is not built; it is written so it can be built in small steps, and so that nothing built meanwhile makes it harder. Part B is the production-readiness list: what is urgent and easy (done now or next), and what can wait.

What was built today toward Part A (so the later work starts from something real): account setup with **target roles chosen by the user** (not a fixed list), CV upload (PDF, Word, text, scans with OCR), public profile links, GitHub reading, scoring that reads the user's profile instead of a file, and a skill vocabulary that is data (`content/skills.yaml`) and was widened after measuring recall.

## Part A. Role-agnostic CareerPilot (design, not built)

### A1. Where the product is tied to software engineering today (honest inventory)
| Area | What is software-specific | Where |
|---|---|---|
| Skills | The vocabulary is technologies (python, aws, docker) | `content/skills.yaml`, `modules/scoring/skills.py` |
| Role titles | A regex that needs "developer / engineer / architect / SDE" in the title | `modules/profile/rules.py`, `modules/apply/matching.py` |
| Seniority | Level words and "years of experience" phrasing | `modules/scoring/skills.py`, `rules.py` |
| Interview preparation | A 45-day SDE curriculum (159 topics), question types built around code | `content/prep/*`, `modules/prep`, `modules/learn` |
| Practice | An in-browser code and SQL runner is the only "practical" mode | `features/practice`, ADR 0007 |
| Research queries | Query templates say "interview questions", "system design", skills | `modules/research/rules.py` |
| Mock interviews | Prompts assume a technical interviewer | `prompts/mock-*` |
| Company check | Eight generic checks; this part is already role-neutral | `modules/verification` |
| Pay | Rupee/LPA first; the pay chain is role-neutral | `modules/apply` |

Not tied to software: the tracker, the apply list's evidence chain, outreach rules, offers, stories, backups, tasks, the architecture explorer.

### A2. The idea: a *domain pack* per field of work
A domain pack is a folder of data (not code) that tells the platform how a field works. Everything role-specific moves into packs; code only reads packs.

```
content/domains/<id>/            e.g. software, data-analytics, nursing, accounting, design, sales
  pack.yaml                      id, name, version, which roles it covers (titles, synonyms, levels)
  vocabulary.yaml                skills, tools, certifications, regulations; aliases; exact-case acronyms
  roles.yaml                     role families, seniority ladder, "years" phrasing, typical titles
  interviews.yaml                the rounds this field really has (technical, case study, portfolio review,
                                 clinical scenario, OSCE, panel, trade test) and what each one asks
  question_types.yaml            which question types make sense (MCQ, explain, case, code, SQL, scenario, calculation)
  practice_modes.yaml            which practice tools apply (code runner, SQL, spreadsheet, case timer, written + rubric)
  research.yaml                  query templates and trusted source types for this field
  scoring.yaml                   weights and rules (for example certifications matter more than "years" in nursing)
  prompts/                       mock-interviewer and grader prompts, versioned (`vN.md`)
  eval/                          sample CVs, job descriptions and expected readings: the pack's own tests
```
A user's profile points at one or more packs (chosen from the target roles at setup, never from a fixed list of people). A job is read with the pack of its role. A role with no pack uses the `generic` pack (plain vocabulary, no practice runner, interview rounds from research only).

### A3. Making a new pack (the part that must stay honest)
1. **Draft**: a research run (the existing agent, same safeguards) collects, from sources the user can open, the usual skills, rounds, questions and typical titles for the role. Every claim keeps its source and quote.
2. **Review**: the owner approves, edits or rejects each part (the same inbox pattern as research findings). Nothing becomes part of a pack without approval.
3. **Test**: the pack must pass its own `eval/` set (extraction accuracy on sample CVs and job posts) before it is marked usable. Below the threshold it stays "draft" and the UI says so.
4. **Version**: packs are versioned; stored readings and scores record the pack version, so a change never silently rewrites history.

### A4. What changes in code (small steps, in this order)
| Step | Change | Risk it removes |
|---|---|---|
| DY1 | Move the skills vocabulary into `content/domains/software/vocabulary.yaml`; loader takes a pack id; behaviour unchanged (golden tests) | Nothing breaks while the shape is proved |
| DY2 | `domain_ids` on the profile (chosen at setup from target roles); `domain` stored on a job | Per-user and per-job domain |
| DY3 | Role title reading driven by `roles.yaml` instead of the developer/engineer regex; title similarity per pack | The apply list and research work for any title |
| DY4 | Question types and practice modes become a registry the pack selects from (the interface already named in ADR 0007 for the runner) | New practice tools plug in without touching Learn |
| DY5 | Interview rounds from the pack; mock interviewer prompt per pack and round | Mock and checkpoints for non-technical roles |
| DY6 | Pack drafting and review screens; `generic` pack | A new field without a developer |
| DY7 | A second real pack built end to end (suggested: data analytics, close enough to test the idea, far enough to prove it), then a third from a non-technical field | The design is proved, not assumed |

Acceptance for the whole idea: a user who is not a software engineer can set up an account, upload a CV, get skills and roles read correctly (measured on the pack's eval set, target 90% of listed skills found and under 5% invented), get a daily list, a prep plan and mock interviews that fit the field, with no code change.

### A5. Risks and what to say honestly
- Quality per field depends on sources and review; without a person who knows the field, a pack is only as good as its sources. The pack status (draft, tested, approved) must always be visible.
- Regulated fields (medicine, law, finance) need extra care: no advice presented as certain; the apply list and prep content must say "check with an official source".
- Language and region: packs and vocabularies are per language; start with English and India/Europe/US/Gulf as the product already assumes.
- Cost: drafting a pack uses the research agent (model + search). Budgets and the daily cap apply; a pack is drafted once, not per user.

## Part B. Production-readiness list

Priority: **U** = urgent and easy (do now), **N** = next (needed before other people use it), **L** = later (scale or polish). Status is as of 2026-11-07.

### B1. Security
| Item | Pri | Status |
|---|---|---|
| Password recovery for the owner: `careerpilot reset-password --email` (signs every session out) | U | **done today** (tested) |
| Page security headers (nosniff, frame deny, referrer, permissions) | U | done earlier |
| Friendly error and not-found pages (no raw crash screen) | U | **done today** |
| CV upload hardening: size, page and text caps; type by content; no XML parser for Word; zip-bomb check; file never stored; 30 s read limit | U | **done today** (tested) |
| Content-Security-Policy for the app pages (the runner workers already have one) | N | not done (H20): Next needs nonces; do with a report-only first |
| Login throttle exists; add per-user rate limits on expensive routes (CV upload, build list, research start) | N | not done |
| Forgot-password by email, email verification, session list and "sign out everywhere" in the UI | N | not done (needs a mail service) |
| Dependency and secret scanning in CI (config exists) | N | CI has never run: needs a GitHub repository (X09) |
| Two-factor sign-in | L | not done |
| Privacy: export all my data, delete my account and everything in it (CV text, profile, jobs, notes), and a plain statement of what leaves the machine | N | not built; needed before any other person uses it |
| A server-log view (the structured log lines for one request or task) next to the Activity page | L | task history and AI calls are on screen; raw logs go to the terminal only |
| Encrypt CV text at rest with a key from the environment | N | not done (the text is stored in the database as plain text) |

### B2. Reliability and operations
| Item | Pri | Status |
|---|---|---|
| Task history per attempt, progress, retry and cancel from the screen; research and the apply list continue from where they stopped | U | **done today** (tested, including a simulated crash) |
| Worker heartbeat (is the worker alive?) | U | not done: "last task finished" is the only sign (B02) |
| Graceful shutdown: finish or release the running task | N | the watchdog frees it after 15 minutes; not instant |
| Database connection loss: pool recycle, retry with backoff on startup | N | not tested |
| Alerts: failed task or missing backup shown where you will see it (email or push) | N | only on screen |
| Off-machine backup copy | N | manual zip by the owner (documented) |
| Point-in-time recovery, replicas, high availability | L | single Postgres by design for now |
| Metrics and tracing (request time, queue depth, model cost per day) | L | structured logs only; no collector |

### B3. Data and AI quality
| Item | Pri | Status |
|---|---|---|
| Dollar budgets per call, run and day (today: tokens) | N | tokens only (E08/E09) |
| Evals for every AI feature with thresholds | N | only notes search has one; research, scoring reading, mock have none (E-group not started) |
| First live run of search, research, GitHub reading and OCR on real data | **U** | **never done**; everything is tested with fakes or generated samples |
| Accuracy measurement of the CV reader on several real CVs | N | measured on one real CV today (skills 29 to 39 found); no precision figure |
| Pay and interview extraction measured on real pages | N | tested on a hand-written table only |

### B4. Product and UI
| Item | Pri | Status |
|---|---|---|
| Layout audit on every page at phone, tablet and laptop sizes (overflow, clipping, target size, one h1) | U | **done today** as an automated test; found and fixed the jobs table on phones |
| Older pages redesigned with the same components (Discover, Insights, Prep, Practice, Ask, Mock, Offers, Stories) | N | headers and controls unified; layouts not redesigned |
| Command palette and keyboard shortcuts | N | not done |
| Settings page (models, budgets, search, backups in one place) | N | not done |
| Invite-only multi-user: invites, admin screen, per-user caps | N | not done (REQ-29, B21) |
| Real-device and screen-reader testing, Firefox and Safari | N | Chrome and axe only |

### B5. Process
| Item | Pri | Status |
|---|---|---|
| CI green on a remote repository | **U** | never run |
| Coverage report and a floor | N | not measured |
| Release and rollback notes, migration downgrade tests | N | drift test only |
| Load test of the API (50 concurrent users) | L | never run |

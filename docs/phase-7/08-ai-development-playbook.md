# 08: AI development playbook (how this project is built, and how it uses AI)

Two different things are covered here, and mixing them up is the most common mistake:
- **A. Building with AI**: Claude writes code for you. The risk is plausible-looking code that was never checked.
- **B. AI inside the product**: the app calls a model (answers, research, grading). The risk is confident wrong output reaching the user.

Both follow the same rule: **the model proposes, deterministic code and a human verify, and every claim is measured.**

Sources used (checked 2026-11-06): Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents); Anthropic docs, [Define success criteria and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests); Claude Code, [Best practices](https://code.claude.com/docs/en/best-practices); GitHub Spec Kit and AWS Kiro (spec-driven development: spec, plan, tasks, implement); Playwright MCP, Stagehand and Browser Use (AI-driven browser testing). Vendor blogs describing these tools are marketing; their claims were not benchmarked here.

## 1. Principles (what mature teams actually do)
1. **Start with the simplest thing.** Anthropic's guidance: prefer a plain prompt, then a *workflow* (fixed code path with model steps), and only use an *agent* (model chooses its own steps) when the number of steps cannot be known. Agents cost more, are slower, and compound errors.
2. **Evaluate before you build.** Write success criteria that are specific, measurable, achievable, relevant and multidimensional. Build the eval set first, grade automatically where possible (exact match, code checks, then LLM graders using a different model, then humans for the rest), and prefer many auto-graded cases over a few hand-graded ones.
3. **Spec first, code second.** The loop is Specify, Clarify, Plan, Tasks, Implement (test first), Verify. Each step leaves a file in the repo. The chat is disposable; the files are the memory.
4. **Give the AI a way to check its own work.** Tests, type checks, linters, a browser. "It looks right" is not a result.
5. **Put rules that cannot have exceptions in code, not prompts.** Hooks, permission rules, import-linter contracts, CHECK constraints, tests. A sentence in CLAUDE.md is a hint; a failing test is a rule.
6. **Keep humans at the irreversible points**: sending anything, deleting, spending, publishing, accepting generated content into the knowledge base.
7. **Tools are an interface to design.** Clear names, examples, hard to misuse (Anthropic calls this the agent-computer interface). Our MCP tools and research tools follow it.
8. **Transparency**: show the plan, the sources, the cost, and what is unverified.

## 2. The lifecycle for every feature (copy this, do not skip steps)
| Step | Artifact (where) | Who | Gate to pass |
|---|---|---|---|
| 1 Intake | Answers recorded in `01-requirements.md` | Owner answers, Claude asks | No open question that changes scope |
| 2 Specify | Feature spec: purpose, users, inputs, outputs, rules, edge cases, acceptance, out of scope (`09-product-spec.md`) | Claude drafts, owner approves | Owner says approved |
| 3 Design | Short ADR if a real alternative existed (`docs/adr/`) | Claude | Alternatives and reversal cost written |
| 4 Eval/test first | Test cases from `10-test-strategy.md` written (failing) | Claude | Tests fail for the right reason |
| 5 Implement | Code in small commits, one task id per commit | Claude | `Done when` of the task passes |
| 6 Verify | Gates, then browser/agent E2E, then failure drill | Claude + AI QA agents | All green; unverified items listed |
| 7 Independent review | A second pass by a fresh reviewer subagent (code-review skill) | Subagent | No unresolved correctness finding |
| 8 Document | Update docs/ADR/primer, tick the task, update `STATUS.md` | Claude | Next session can resume |
| 9 Accept | Owner tries it | Owner | Owner accepts or lists changes |

## 3. Roles
- **Owner**: product owner and approver. Answers intake questions, tries the result, approves anything that spends money, sends data to a third party, or changes the plan.
- **Claude (main session)**: engineer. Writes specs, tests, code, docs. Never claims what it did not run.
- **Subagents** (separate context windows): *explorer* (read-only search), *reviewer* (fresh eyes on a diff), *tester* (writes adversarial tests). Use them for work whose result is a short report, so the main context stays small.
- **AI QA agents**: drive the real app in a browser (section 6 of `10-test-strategy.md`).

## 4. Intake questions (ask these; record the answers)
Claude must ask the questions for an epic *before* starting it, offering a recommended default so the owner can reply "default".
**Product**
1. Who uses this in six months: only you, or friends/other job seekers too? (changes auth, tenancy, hosting) Default: only you now, design so more users is possible.
2. Which roles and companies are you targeting now? (seeds the first research runs) Default: backend/full-stack Python and data engineer roles in India and remote.
3. Weekly time budget for prep and for building? Default: 2 hours/day build cap as before.
4. What does "I am ready" mean for you? (shapes checkpoint pass marks) Default: 80% on a checkpoint across all high-priority topics, twice, a week apart.
**Look and feel**
5. Show 2 to 3 apps you like (screenshots welcome; Claude can read images). Default: Linear (calm density), Vercel dashboard (clarity), Huntr (board).
6. Name and logo: keep "CareerPilot" with the paper-plane mark in `assets/`? Default: keep.
7. Language of the interface: English only? Default: yes.
**AI usage**
8. Is a Claude API key available, and what monthly budget is acceptable? Default: key in `.env`, 5 USD/day cap, hard stop.
9. May private notes and answers be sent to Claude? (ADR 0008 says yes when a key is set.) Default: yes for study content, never for the profile file, contacts' emails or backups.
10. Which search source for research: Brave Search API (needs a key), Anthropic web search (priced per 1,000 searches, checked 2026-11-06 at $10), or manual paste only? Default: Brave behind an interface, manual paste always available.
**Operations**
11. Docker for the whole stack, or keep native dev + Docker Postgres? Default: add Docker for everything, keep native dev working.
12. Will this stay on your laptop or go to the cloud later? Default: laptop; keep the cloud path open.
13. Where do off-machine backups go? Default: a folder you sync (OneDrive/Drive).
**Quality**
14. Browsers and devices to support? Default: latest Chrome/Edge/Firefox desktop; responsive down to a phone for reading.
15. Accessibility target? Default: WCAG 2.2 AA.

## 5. Using AI inside the product: which pattern for which feature
| Feature | Pattern | Why this and not an agent | Human gate |
|---|---|---|---|
| Ask my notes | Workflow: retrieve, then one answer step with citations | Steps are known | Citation check in code |
| Company page review | Workflow: fixed pages, one extraction step, code verifies quotes | No tool loop needed | Owner sees quotes |
| Scoring reading | Single call, schema output | One step | Score computed by code |
| Outreach draft | Prompt chaining: facts check (code), draft (model), lint (code) | Fixed order | Owner approves; nothing sends |
| Interview intel extraction | Workflow per source + quote check | Fixed | Owner reviews |
| **Interview research (new)** | **Orchestrator-workers**: planner proposes queries, workers fetch/extract pages in parallel under budgets, code dedupes and verifies, **evaluator** step flags weak items | Pages and queries unknown in advance, but bounded | **Inbox: owner approves every item** |
| Question generation (MCQ) | Generator + independent **evaluator-optimizer** (second call answers blind, code checks grounding) | Wrong questions are harmful | Owner can edit/reject |
| Short-answer grading | Rubric-based LLM grader + deterministic keyword/regex checks | Subjective | Shown as "model's opinion" with the rubric |
| Mock interviewer | Conversation workflow with state in the DB | Turn-based | Scores labelled opinion |
Guardrails for all: data wrapped as untrusted (`data_block`), structured output with validation and one repair, per-call and per-run token budgets, per-day cap, audit row per call, prompts as versioned files, golden-set evals in CI (fakes) and a periodic live eval (real key), kill switch (`ANTHROPIC_API_KEY` empty = everything degrades to non-AI paths).

## 6. AI-assisted engineering practices (this repo)
- `CLAUDE.md` stays short and contains only what cannot be inferred from the code. Rules that need enforcement become tests/hooks (task T-X05 adds a Stop hook that runs the gates).
- Project **skills** (T-X03): `careerpilot-dev` (workflow + gates), `ui-review` (design-system checklist), `write-eval` (how to add a golden case). The Anthropic `frontend-design` skill was read (2026-11-06): its advice (one memorable element, restrained palette, real microcopy, keyboard focus, reduced motion, remove one unnecessary element) is adopted in `02-design-system.md`; its warning against the "SaaS card kit" is reconciled by our rule: *restraint over decoration*. Install only after reading the files.
- **Parallel work** only when tasks touch different files (separate worktrees); never two writers on one file.
- **Context hygiene**: long outputs go to files; subagents for searches; commit small; update `STATUS.md` at every milestone, not only at the end.
- **Cost hygiene**: reviewers and explorers can use a cheaper model; large refactors use plan mode first.

## 7. Session handoff protocol
**Start of session**: read `docs/phase-7/STATUS.md`, `07-tasks.md` (find next task), `git log -5`, `git status`. Run the gates once to know the baseline. Do not re-research what the docs already record.
**During**: one task id per commit; if a task changes scope, edit the plan file first.
**End of session (also when context is almost full)**: tick finished tasks with commit ids; write in STATUS.md: where we are, what is half-done (file names), what to do next, open questions for the owner, anything surprising; commit docs. If the session is cut abruptly, the previous commits plus STATUS.md must still be enough.
**Memory notes** (`~/.claude/projects/D--careerpilot/memory/`) hold the owner's profile, working style and the pointer to docs; they never replace the docs.

## 8. Definition of Ready (before coding a task) and Done
Ready: spec exists, intake questions answered, test cases listed, dependencies done, size <= 3 hours (otherwise split).
Done: tests (unit + API + where relevant browser) pass; owner-scoping and CSRF tests included for new routes; failure behaviour tested; types/lint/contracts green; docs and primer updated; `STATUS.md` updated; unverified parts stated in the commit message.

## 9. Anti-patterns to refuse
Building from a chat message with no spec. Claiming "works" from a type check. Letting a model decide a verdict, score or permission. Silent fallbacks that hide failures. Copying a library's default look. Generating test data and expected answers from the same prompt (the grader must not share the generator's mistakes). Large untested prompts edited in place. Unbounded agent loops (always a step, page, token and time budget).

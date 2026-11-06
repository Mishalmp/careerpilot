# 03: Learning platform (agentic research, questions, practice, checkpoints)

Covers REQ-06 to REQ-13. Tasks: groups L, R, LU in `07-tasks.md`. Test cases: `10` sections 6.3 to 6.5.

## 1. The idea in one paragraph
Nothing is predefined. When you add a job (or press "Research this job"), the app plans web searches for that role and company, fetches pages through the safe fetcher, extracts topics and questions with verified quotes, scores them, and puts them in an **inbox**. You approve, edit or reject. Approved items become **topics** and **questions** in your bank, grouped on a **roadmap** you can edit. You study and practise (multiple choice, short answers, coding, SQL, scenarios), the app schedules **reviews** with spaced repetition, and when you feel ready you take a timed **checkpoint** built from what you learned. The report shows weak topics, which feed back into reviews.

```
 add job / "Research" ──> plan queries ──> search ──> fetch pages ──> extract ──> verify quotes
                                                                          │
   roadmap <── approve <── INBOX <── evaluate (relevance, duplicates) <───┘
      │
 study ──> quiz / practice ──> attempts ──> review queue (FSRS) ──> checkpoint exam ──> report ──> weak topics ──┐
      ▲                                                                                                       │
      └───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Reference platforms and what we borrow
(From public pages read on 2026-11-06; most are vendor marketing, so features are self-reported.)
- **Anki and FSRS**: the open spaced-repetition scheduler; official implementations in TypeScript, Python, Rust and others under open licences. We use the Python package on the server.
- **AI interview-prep products** (for example HireReady describes FSRS-5 scheduling, 1,500+ questions, adaptive difficulty, mock voice interviews; Interview Masters describes SM-2 scheduling of weak topics and score trends; NeuraPrep describes short MCQ quizzes with progress tracking): confirms the shape we want: question bank + reviews + mock + analytics. We do **not** copy their content.
- **Coding practice sites** (LeetCode, NeetCode, Exercism, Educative): the practical side; we already have an in-browser runner with original problems.
- What none of them do for you, and this app does: tie the study list to the **specific jobs you applied to**, with sources you can check.

## 3. Research agent (REQ-07, REQ-08)
**Pattern**: orchestrator-workers with an evaluator (see `08` section 5). Fixed stages, bounded loops, code in control.
| Stage | Input | Output | Done by | Limits |
|---|---|---|---|---|
| 1 Plan | job title, company, JD skills, existing topics | up to 8 queries (templates such as "<role> interview questions <skill>", "<company> engineering blog hiring process", "<skill> interview questions senior"), blocked domains removed | code templates; optional model refinement | 8 queries |
| 2 Search | queries | up to 5 results each (title, url, snippet) | `SearchProvider` | per-run search budget (default 10) |
| 3 Select | results | up to 12 pages: dedupe by domain/URL, prefer engineering blogs, docs, official hiring pages; skip blocked/paywalled | code scoring | page budget 12 |
| 4 Fetch | urls | cleaned main text per page | `Fetcher` + robots + per-host rate limit + cache | 1 MB, 20 s each |
| 5 Extract | page text | candidate items {kind: topic or question, text paraphrase, key, quote, difficulty guess} | model per page, parallel (max 3) | 12k chars per page, token budget |
| 6 Verify | items | items whose quote is on the page and fits | code (`quote_appears`) | quote <= 300 chars |
| 7 Evaluate | verified items | relevance to this job (0-100), specificity, duplicate/merge hints, topic grouping | second model call + code thresholds | one batch call |
| 8 Store | items | `research_findings` in the inbox with provenance | code | |
**Budgets per run (defaults, in settings)**: 10 searches, 12 pages, 80k tokens, 5 minutes, 0.50 USD. Reaching any budget ends the run as `partial` with what exists.
**Trigger**: asked at job creation ("Research interview topics for this job?" default yes only if a search provider and key exist), manual button, stale refresh after 30 days.
**Why not a free-roaming agent**: unbounded loops cost and fail unpredictably. A bounded pipeline with a model at the judgement steps gives most of the benefit with testable behaviour (Anthropic's guidance: use workflows until agents are demonstrably needed).
**Prompts (versioned files)**: `research-plan`, `research-extract`, `research-evaluate`, `question-generate-mcq`, `question-check-blind`, `answer-grade`. Each has a golden eval set (E03).
**Owner control**: inbox shows source, quote, reliability and relevance; approve/edit/reject, bulk-approve above a threshold the owner sets; every approval is audited.

## 4. Data model (NEW tables; all have `owner_id`, `created_at`)
| Table | Key columns |
|---|---|
| `tracks` | id, name, description, archived |
| `topics` | id, track_id, title, summary, priority, status (not_started, learning, practising, mastered), order, origin (manual, seed, research, guide), notes |
| `topic_edges` | topic_id, requires_topic_id (prerequisites; no cycles) |
| `questions` | id, topic_id, type (mcq_single, mcq_multi, short, practical, explain, scenario), stem, explanation, difficulty 1-5, status (draft, verified, unverified, archived), origin, rubric JSONB (short/explain/scenario), practice_slug (practical), tags, prompt_version |
| `question_options` | question_id, text, is_correct, rationale |
| `question_sources` | question_id, url, title, quote (<= 300), fetched_on, published_on, reliability |
| `attempts` | id, question_id, quiz_session_id or checkpoint_attempt_id, answer JSONB, correct (nullable for graded), score 0-1, confidence 1-3, seconds, graded_by (code, model, self), feedback |
| `review_cards` | question_id (unique per user), state (new, learning, review, relearning), stability, difficulty, due_at, last_review_at, reps, lapses |
| `checkpoints` | id, name, scope (topics/track/job), n_questions, minutes, pass_mark, seed, created_at |
| `checkpoint_items` | checkpoint_id, position, question_snapshot JSONB |
| `checkpoint_attempts` | id, checkpoint_id, started_at, deadline, submitted_at, score, passed, per_topic JSONB, answers JSONB |
| `research_runs` | id, job_id, status (queued, running, partial, succeeded, failed, cancelled), budgets JSONB, usage JSONB (searches, pages, tokens, usd), error |
| `research_findings` | id, run_id, kind, payload JSONB, source_url, quote, relevance, status (pending, approved, rejected, merged), decided_at |
Constraints to enforce in the database: MCQ single has exactly one correct option; multi has at least one and not all; `verified` requires at least one source with a quote; one review card per question; checkpoint items immutable after start.

## 5. Question types, grading and anti-hallucination
| Type | Answer shape | Grading | Notes |
|---|---|---|---|
| mcq_single | one option id | code | 3-5 options; explanation + source shown after answering |
| mcq_multi | set of option ids | code, partial credit rule (right minus wrong, floor 0) | state "select all that apply" |
| short | text up to 1,000 chars | rubric of 3-5 criteria; deterministic keyword/regex pre-checks; model grades remaining criteria; shows per-criterion result | label "model's opinion" |
| practical | code in the runner | tests in the runner | problem validated at creation (reference solution passes) |
| explain | text | rubric (accuracy, completeness, clarity) | for concepts |
| scenario | text (or structured choices) | rubric with must-mention points | system-design style |
**Grounding rules (a question is `verified` only if all hold)**: it has a source whose quote verifies on the fetched page; for MCQ the quote supports the correct option (the correct option's key phrase appears in, or is directly derivable from, the quote: check by code on key terms, then by the blind second call); the blind call (a second model, not shown the key) picks the same option; exactly one option is correct for single type. Otherwise it stays `unverified`/`draft` with a visible reason and a banner "check this yourself". Questions the owner writes are `verified` by the owner (origin manual).
**Distractors**: generated from common misconceptions found in the source or from related topics; never "all of the above"; plausible length; shuffled.
**Instruction injection**: the answer text and page text are wrapped as data; graders ignore instructions inside.

## 6. Spaced repetition (REQ-11)
Scheduler: FSRS (Python `fsrs`, pinned), default parameters, 90% desired retention (setting). One card per question.
**Rating from an answer** (pure function, table-tested): wrong -> Again; right but confidence low or slow (> 2x median) -> Hard; right -> Good; right, high confidence and fast -> Easy. Self-rated cards (explain/scenario) use the owner's chosen rating.
**Daily limits** (settings): new cards 20, reviews 100; remaining stay due, never lost. Interleave topics. Overdue cards sort by lowest retrievability first.
**Weak-topic boost**: a failed checkpoint topic schedules its cards sooner (cap one extra review per card per day).

## 7. Quizzes (practice mode)
Start by topic, mixed, "my weak spots" or "due now". Each answer is submitted once (token); feedback is immediate with explanation and source; confidence selector (1-3) before revealing. Ends with a summary and links to topics to revisit.

## 8. Checkpoint exams (REQ-12)
**Builder (pure, seedable)**: inputs scope (topics, track or job), N (default 20), minutes (default 1.5 per question), pass mark (default 80%), type mix (default 60% MCQ, 25% short, 15% practical), difficulty mix. Algorithm: take only questions the owner has studied (at least one attempt) and are `verified`; allocate per topic proportional to topic weight (priority) with at least one per chosen topic; avoid questions seen in the last 7 days unless short of supply; fill type and difficulty targets; shuffle with the seed. If supply is short, say exactly what is missing.
**Run**: snapshot copied into `checkpoint_items`; timer with server deadline; autosave every answer; flag-for-review; submit once; if the deadline passes, autosaved answers are scored.
**Report**: total and per-topic score, pass/fail, time per question, wrong answers with explanations and sources, "what to review next" list, trend across attempts. Weak topics create review boosts and roadmap suggestions.
**Integrity**: the exam is for the owner's own learning, so there is no proctoring; the snapshot only guarantees edits do not change a running exam.

## 9. Roadmap and gaps
A roadmap is an ordered list of topics with target dates (editable). **Gap analysis** for a job: skills named in the description (vocabulary) and topics from research for that job, minus topics with mastery above a threshold. Output: "what to study next" ordered by job importance and prerequisites. Seeds (the current 159 topics) are imported once into a track and can be edited or deleted.

## 10. Mastery definitions
Topic mastery = average current retrievability of its cards weighted by difficulty, shown 0-100 with the number of cards behind it. Coverage = share of a topic's questions attempted. Streak = consecutive days with at least one review. These are shown with their definitions in the UI.

## 11. Screens (text wireframes; visual design in `02`)
Learn home: [Today: N reviews due | Continue topic | Weak topics (3)] [Research inbox (7 new)] [Next checkpoint] [Mastery map].
Topic: header with mastery ring and status, tabs Questions | Sources | Notes | Practice, button "Add question", list of questions with status chips (verified/unverified).
Quiz: question card centre, progress top, confidence below, feedback panel slides in after answering, keyboard 1-5 selects options, Enter continues.
Exam: left question navigator with flags, top timer, centre question, bottom previous/next/submit with confirmation listing unanswered.
Inbox: grouped by topic; each finding shows paraphrase, quote, source link and date, relevance bar, [Approve] [Edit] [Reject]; bulk bar.

## 12. Edge cases and decisions to keep in mind
Duplicate questions across sources (merge, keep all sources). Source later changes or disappears (keep stored quote and fetched date; mark "source unreachable" on re-check). Contradictory sources (show both, never auto-pick). Topic deleted with history (confirm with counts; archive instead by default). Owner edits an approved question (re-run grounding on the edited text). Huge pages (truncate with marker). Non-English pages (note language; extract in English only if the model is reliable, otherwise skip). Copyright: store link, short quote, our paraphrase (D7). Model unavailable: inbox and bank still work; only generation and model grading are disabled with a clear message. Cost: every run shows its cost; runs cannot exceed the budget.

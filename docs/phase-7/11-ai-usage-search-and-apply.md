# 11: AI access, model context, search APIs, security and daily apply (decisions and rules)

Written 2026-11-06. "Verified" means read on the vendor's own page or run here; "reported" means only third-party pages said it; "my estimate" is arithmetic on verified prices. Re-check prices before paying.

## 1. Running the AI features without an API key
**Fact**: a Claude Pro subscription does not include an API key; API use is a separate Console account billed by prepaid credits (reported by Anthropic's help article via search; the $5 minimum is reported by third parties, not confirmed on Anthropic's own page).

| Option | Cost | What it means | Status here |
|---|---|---|---|
| A. Console key with a small prepaid top-up | Pay per token (see 1.2) | The supported way for an app. Cheap model for reading, main model for judgement | Built; never called live (task E01 needs your key) |
| B. `claude -p` / Agent SDK logged in with your plan | Uses plan limits | Plan login is documented as for ordinary individual use with Claude's own apps; wrapping it inside your own application is ambiguous (plan.md section 15). Slower, less control | Not built, off by default |
| C. Free local model (Ollama) behind the same interface | Free, uses your CPU/GPU | Quality for extraction and grading is unproven; would need the eval set (E03/E04) to decide | Not built |
| D. No AI | Free | Everything deterministic works (below) | Works today |

**What works with no key** (tested with the app's own test suite, which runs without one): job tracker, company-check verdict rules (with findings you enter by hand), fit score rules, Learn (manual topics and questions, multiple choice marked by code, FSRS reviews, checkpoint exams), CV reading (rules), architecture explorer, live status, practice runner, notes search (returns the matching passages without a written answer), research inbox (manual only). **Needs a key**: research extraction, company-page reading, written answers with citations, mock interviews, model grading of written answers.

### 1.2 What it costs (prices verified on Anthropic's pricing page 2026-11-06; usage is my estimate)
Per million tokens, input / output: Haiku 5.5 **0.10 / 0.50** USD (prompts up to 100k tokens), Sonnet 5.5 2 / 10, Opus 5.5 4 / 20.
| Task | Tokens (estimate) | Haiku 5.5 | Sonnet 5.5 |
|---|---|---|---|
| One research run (12 pages x ~3.4k in, ~0.6k out each) | 41k in, 7k out | **about 0.008 USD** | about 0.15 USD |
| One "Ask my notes" answer | 2.5k in, 0.4k out | about 0.0005 | about 0.009 |
| One mock interview (about 16 calls) | about 48k in, 8k out | about 0.009 | about 0.18 |
Heavy day (5 research runs, 10 questions, 1 mock): about 0.04 USD with the cheap model on the reading steps plus about 0.27 USD on the judgement steps, **about 0.3 USD a day, about 9 USD a month at the very most**. A 5 USD top-up lasts one to two months at light use. Keep the daily cap (`CAREERPILOT_LLM_DAILY_TOKEN_CAP`, default 200,000 tokens); a dollar cap is task E09.
**Built today**: bulk-reading prompts (`research-extract`, `intel-extract`, `company-pages`, `jd-reading`) use `llm_model_light` (Haiku 5.5); everything else uses `llm_model` (Sonnet 5.5). Both are settings, the list of light prompts is a setting, and the model really used is recorded in `llm_calls`. Test: `tests/test_llm_models.py`.

## 2. Model context: what to set and what never to send
**Set (in code or settings)**
- One narrow door: every call goes through `core/llm.call_llm`/`call_llm_json` (daily token cap, one audit row per call with the model, tokens, latency, status).
- Prompts are versioned files (`prompts/<name>/vN.md`); a used prompt is never edited, a new version is added. System text is the file; untrusted text goes only in the user message inside `data_block(...)`.
- `max_tokens` per prompt (in its file); page text is cut to 12,000 characters before sending; notes passages are limited to what retrieval returned.
- Structured output: the reply must be one JSON object that validates against a schema; one repair attempt with the validation error; then fail clearly, store nothing.
- Request shape is the plain one: `output_config.effort = "low"`, no `thinking`, `temperature`, `top_p`, `top_k` or assistant prefill. Anthropic's error table says non-default sampling parameters, `budget_tokens` and assistant prefill return 400 on Haiku 5.5, and `thinking: disabled` returns 400 on Sonnet 5.5 and Opus 5.5, so sending none of them is the safe default (documented, not tried live).
- Budgets: per run (searches, pages, tokens) and per day. Reaching one ends the run as "partial" with a message.
- Cost levers to try **after measuring** with evals (E10): prompt caching for long repeated prefixes, the Batch API for non-urgent work, a still cheaper model for easy prompts.

**Never send to a model or search service**: the profile file (`content/private/profile.yaml`), contact emails, passwords, session cookies, backups or any key, the CV text (only skills and role titles derived from it go into search queries), and anything from LinkedIn/Indeed/Glassdoor/Naukri pages (they are blocked from fetching). Private notes go to the model only with a key set (decision D6) and only the matched passages.

**Do not**: let a model compute a verdict, score, state change or permission (code does); let a model choose a URL to fetch outside the search results and the safe fetcher; run model-written code on the server; add a tool that sends, deletes or changes settings; store a model's quote that is not found in the fetched page; trust a model's "verified".

## 3. MCP rules (checked against Anthropic's `mcp-builder` guide, reviewed and installed in `.claude/skills/`)
| Rule from the guide | Our status |
|---|---|
| Tool names carry a service prefix so they cannot collide with other servers | **Done 2026-11-06**: every tool is `careerpilot_<action>`; test enforces it; the built-in prompts were updated to the new names (a test caught the stale names) |
| Annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) on every tool | Done (READ / WRITE sets) |
| Descriptions match behaviour; atomic tools | Done; new tools say their text is untrusted |
| Validate all inputs with schemas; do not leak internals in errors | Done (`ToolError` for user-facing, others hidden) |
| stdio for local single-user; log to stderr, never stdout | Done (stdio only) |
| Pagination with `limit` and metadata (`has_more`, `next_offset`, `total`) | **Gap**: `limit` is respected and capped, metadata is not returned (changing list results to objects breaks clients; planned in H17) |
| Markdown and JSON response formats | **Gap**: JSON only; not needed for one local user |
| Remote transport with OAuth 2.1, DNS-rebinding protection | Not applicable until stage 3; do not expose the server on a network before adding auth |
Our additions beyond the guide: writes preview until `confirm=true` and are audited; no tool can send, delete or change settings (a test searches tool names); the server instructions tell the model that returned text is data.
New read-only tools: `careerpilot_get_learning_status`, `careerpilot_list_research_inbox`. Approving or rejecting findings is deliberately not a tool.

## 4. RAG rules (notes search), as built and as to be kept
1. Heading-aware chunks, local embeddings (no cost, nothing leaves the machine), Postgres vector + full-text search merged by reciprocal rank fusion.
2. A similarity gate: below it, answer "not in your notes" and show the nearest passages.
3. The model answers only from the passages and must cite passage ids; an answer with a missing or invalid citation is withheld.
4. Quality is measured, not felt: `careerpilot eval-rag` before and after every change to chunking, embeddings, ranking or prompts.
5. Retrieved text is untrusted: it is wrapped as data and cannot change rules or call tools.
Planned: `embedding_version` per chunk (H12), faithfulness check and a bigger eval set (H14), reranker only if the eval shows a need (H13).

## 5. Security checklist (senior review; status is honest)
| Area | Status |
|---|---|
| Sessions: HttpOnly, SameSite=Lax, CSRF header on unsafe methods, a test walks every route | Done |
| Login throttle persistent | **Open** (in memory today, B08) |
| SSRF: one fetcher, private ranges refused on every redirect, size/time caps, blocked sites | Done, extended suite planned (H21) |
| Prompt injection: data blocks, schema-validated output, quotes checked against the page, human approval before anything enters the bank | Done for research and company check; adversarial corpus planned (R13) |
| Secrets only in the environment; never in the repo; `.env` ignored; secret scanner in CI | Partly: ignored yes; scanner is task X07 |
| An earlier commit once carried a password line: found, removed, amended before any push | Done; the lesson is task X07 |
| Page CSP | **Open**: only the code-runner workers have one (H20) |
| Supply chain: dependencies audited in CI (CI never ran), skills reviewed and pinned (`.claude/skills/PROVENANCE.md`), no catalogue installs | Partly |
| Per-user isolation: `owner_id` on every query and a cross-owner test per resource | Done for all current modules |
| Cost abuse: daily token cap and per-run budgets | Done (tokens); dollars E09 |
| Data minimisation to model/search vendors (section 2) | Done by rule; a visible "what leaves this computer" screen is P15 |
| Backups: encrypted, key apart, restore only into a new database, tested in containers | Done |
| Audit log of writes through services | Partial (B06) |

## 6. Free and cheap search and data APIs
| Source | Free allowance | Paid | Verified how | Good for |
|---|---|---|---|---|
| **SearXNG** (self-hosted) | Unlimited, no key; engines vary (DuckDuckGo showed a CAPTCHA, others answered) | none | **Run here**: 38 results, adapter parsed them | Default for research |
| **Tavily** | **1,000 credits a month, no card**; a basic search = 1 credit | 0.008 USD per credit pay-as-you-go | Official pricing and API reference | Fallback; about 100 research runs a month |
| **Exa** | **10 USD credit a month**, no card | 4 USD per 1,000 lite searches, 7 per 1,000 auto | Official pricing page | Semantic search; not built |
| **Serper** (Google results) | 2,500 free queries, no card | cheaper than most (a third-party figure is about 1 USD per 1,000; not confirmed) | Free tier on the official page | Not built |
| **Brave Search API** | about 5 USD of monthly credit (about 1,000 queries), card required (reported) | about 5 USD per 1,000 (reported) | Third-party only; official page unreadable | Adapter exists, least verified |
| **GitHub REST API** | 60 requests/hour without a token, 5,000 with one | | Official docs | Finding example repositories, not interview content |
| **Hacker News (Algolia)** | No key; reported limit 10,000 requests/hour per IP | | Third-party only | "Ask HN" interview threads; not built |
| **Reddit Data API** | Reported: free for non-commercial use at 100 requests/minute with OAuth, approval can take weeks, some sources report the public API closing in 2027 | commercial only | Third-party only, sources conflict | **Do not depend on it** |
| Job boards (Greenhouse, Lever, Ashby public job feeds) | Free, no key | | Used by Discovery since Phase 5 | Finding jobs |
**Recommendation for one daily user**: SearXNG as the default (free, tested), Tavily as the no-card backup (set `CAREERPILOT_SEARCH_PROVIDER=tavily` and the key). Reddit and review sites are not worth the terms risk; paste a page by hand when you find something good. Only links come back from search; every page is read through the safe fetcher.

## 7. "Auto apply daily": what is possible and what I recommend
**Decision needed from you, because it changes a standing rule** (CLAUDE.md: anything that leaves the machine, including applications, needs your explicit approval; there is no send action; LinkedIn, Indeed, Glassdoor and Naukri are never automated).

Why fully automatic submission is not recommended, in plain terms:
1. **Terms and bans**: the big boards forbid automated applying and ban accounts that do it. The app already refuses to fetch them.
2. **CAPTCHAs and bot checks**: automating past them is something I will not build or run.
3. **Quality**: a wrong claim or a wrong company in an automatic application costs more than a missed one; recruiters notice mass applications.
4. **No candidate API**: as far as I know (not verified) the public Greenhouse, Lever and Ashby feeds the app reads are read-only for candidates; applying goes through each employer's form.

**What I recommend instead: assisted apply, fully rule-driven and editable**
- Every day the worker ranks new and tracked jobs with your editable policy and puts the best few in an **Apply queue** with everything prepared: the company-check verdict and evidence, the fit score and reasons, a tailored message draft (existing outreach drafter, lint and guards), the apply link, and a "why this job" line.
- You open the queue, review (one minute each), and press **Open apply page** (and mark applied). The app never submits for you. This keeps the daily habit and the speed, and keeps you inside every site's terms.
- The **policy is a file you own** (`content/private/apply-policy.yaml`) so you can change the logic any time without code:
```yaml
daily_limit: 3
min_fit_score: 70
require_company_verdict: [genuine]          # never suspicious
roles_from: profile                         # role titles come from your CV profile
regions: [India, Remote (Global)]
work_modes: [Remote, Hybrid]
min_salary_lpa: null
skip_companies: []
skip_if_applied_within_days: 90
prefer_posted_within_days: 14
sources: [greenhouse, lever, ashby, manual]
auto_submit: false                          # locked: the app has no submit action
```
- Tasks (new group A in `07-tasks.md`): A01 policy file schema and loader with validation, A02 pure ranking rules with tests, A03 apply-queue table and daily task, A04 queue API, A05 queue screen, A06 "why this job" explanation and policy dry-run ("what would have been chosen yesterday"), A07 per-day audit, A08 measure: did queue picks lead to replies (uses Insights).
- If you still want a stronger automation later, the safe ladder is: queue (above) -> pre-filled email drafts you send yourself -> only for companies that publish a real application API or accept email applications, a one-click send after your approval. Each step stays behind your approval.

## 8. Things I changed because I was confident (2026-11-06)
1. MCP tools renamed with a `careerpilot_` prefix; stale names in prompts and docs fixed; tests updated and extended.
2. Two read-only MCP tools for Learn and the research inbox.
3. Per-task model choice (cheap model for bulk reading) with tests; request shape checked against Anthropic's error table.
4. Tavily search adapter (official API shape), tests, settings, compose and `.env.example`.
5. Three official Anthropic skills reviewed and installed at project scope, pinned, with a provenance file; the catalogue tool itself not installed.

## 9. Still unverified (each has a task)
No live Claude call (E01). Tavily and Brave not called with real keys. The `effort` parameter on Haiku 5.5 is documented but not tried. All price figures can change.

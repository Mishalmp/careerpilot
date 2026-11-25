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

### 7.1 What was built (2026-11-07): the assisted daily list

The owner asked for a daily list where every job is "one step away from applying", with pay and interview information found step by step and labelled with where it came from, so nothing is trusted blindly. Built as `apps/api/src/careerpilot/modules/apply/` and the `/apply` page. **Approval triggers tracker changes and opens the apply page; it never submits a form on an external site** (terms of service, CAPTCHAs, and every form differs; the project rule "no send/submit action" still holds and a test proves the API has no such route).

Daily flow (worker task `apply_queue`, built once a day after `CAREERPILOT_APPLY_HOUR`, default 9, for users whose CV profile has skills or titles; the "Build today's list" button queues one more):
1. Read the policy file (`content/private/apply-policy.yaml`, else `content/apply-policy.example.yaml`, else defaults). A wrong file stops the build with a plain list of problems (it never silently falls back). There is deliberately no auto-submit key.
2. Candidates: tracker jobs that are New or Shortlisted and never listed before. Policy hard rules remove some (regions, work modes, skipped companies, needs an apply link); a field the post does not state never excludes a job.
3. Score 0-100 with `matching.py`: 60 for the share of the post's skills you have, 30 for a title like one on your CV, 10 for a post under 14 days old. Unknowns get a neutral value and the reason says so. Keep scores at or above `min_match_score`, best first, up to `daily_limit`.
4. For each job: company check (the existing eight checks and red flags through the safe fetcher). The job is **held back** (status blocked, shown with the reason) only on hard evidence: a raised red flag or two failed checks. Missing information never holds a job back. Held-back jobs do not use the day's limit, and you can still approve one yourself.
5. Pay, by levels; the first level with an answer wins and the levels that had none are listed ("Where I looked"):
   1. stated in this post (salary field or description), or your own tracker estimate, labelled as yours;
   2. the same job on another site (search hits that name the company and a similar title; a page is opened to compare skills, 60% or more in common = same job);
   3. an earlier or similar post by the same company (your tracker, then web pages about the company);
   4. similar roles at other companies: a market range, labelled "not this company".
   Several figures give a range (the middle half when there are four or more) and a median. Currencies are never mixed or converted (no exchange rate is fetched); rupee figures win when present.
6. Interview information, same idea: the post itself, this company's process on a page, typical for similar roles (labelled "not this company"). Found by rules: the sentences that best describe a process, copied from the page, with the link.
7. "Also listed on": other sites that list the same company and role, with skills in common when the page was read. Sites that forbid automation (LinkedIn, Indeed, Glassdoor, Naukri) appear as links only: their pages are never opened and their search snippets are never used as evidence.

Limits per job (cost control): at most 5 searches and `max_web_pages_per_job` pages (default 3). With 3 jobs a day that is about 15 searches a day, 450 a month, inside Tavily's free 1,000 credits.

What you do: open `/apply`, read a card, follow the sources. **Approve** makes the job Shortlisted in the tracker. **Open the apply page** is a plain link; you apply yourself. **I applied** sets Applied - Pending with a follow-up in 7 days. **Skip** leaves the tracker alone and the job is not listed again.

Honest limits:
- No model reads anything in this feature, so there is no prompt-injection path and no cost, but also no understanding: pay figures come from regular expressions (tested on a table of formats, not on thousands of real pages) and can be misread; always follow the quote to the source.
- Search quality is whatever your provider returns. A search service must be set up (`CAREERPILOT_SEARCH_PROVIDER`), otherwise only the post and your tracker are used and the card says so.
- Not run against a live search service or real job pages yet; the tests use a fake search service and fake web. First live run: build the list with SearXNG running and read the cards critically.
- Candidates come only from the tracker. Feeding the Discover inbox into the list is a follow-up.
- Not built from the original design: a tailored message draft per job, the policy dry run (A06), the audit summary (A07), reply measurement (A08), recording the click on "open the apply page".

## 8. Things I changed because I was confident (2026-11-06)
1. MCP tools renamed with a `careerpilot_` prefix; stale names in prompts and docs fixed; tests updated and extended.
2. Two read-only MCP tools for Learn and the research inbox.
3. Per-task model choice (cheap model for bulk reading) with tests; request shape checked against Anthropic's error table.
4. Tavily search adapter (official API shape), tests, settings, compose and `.env.example`.
5. Three official Anthropic skills reviewed and installed at project scope, pinned, with a provenance file; the catalogue tool itself not installed.

## 9. Still unverified (each has a task)
No live Claude call (E01). Tavily and Brave not called with real keys. The `effort` parameter on Haiku 5.5 is documented but not tried. All price figures can change.

## 10. Finding jobs, applying at volume, and what it costs (2026-11-08)

### 10.1 Where jobs come from, and what is missing
| Source | Status | Notes |
|---|---|---|
| Company boards (Greenhouse, Lever, Ashby) | built, live-tested | one request per board per day; you must know the company's board name |
| Free feeds: Remote OK, Remotive, We Work Remotely, Himalayas, Arbeitnow | built (checked live for shape on 2026-11-08) | no key. Terms: link back and name the source (shown on each job); Remotive delays jobs 24 h and asks for at most 4 reads a day (we read once) |
| LinkedIn, Indeed, Glassdoor, Naukri | **not read, by design** | their terms forbid automation; scraping gets accounts banned. Add such a job yourself from the Jobs page with its link and the app researches it |
| Adzuna API (**paid**: 8 GBP a month for 5,000 calls a month and 500 a day; the free plan is 25 test calls) | not built; earlier text called this a free key, which was wrong | a search API: keywords and cities from your searches. Official limits not verified (sources disagree: 250 a day or about 1,000 a month) |
| Jooble API (key by request form; price and limits not stated on its page) | not built | POST search; India and UAE coverage not confirmed |
| JSearch (Google for Jobs data, includes big boards) | not built | small free plan, paid beyond; a licensed way to see listings that also appear on LinkedIn or Indeed |
| Job-alert emails forwarded to the app | not built | would cover Naukri and LinkedIn alerts without reading their sites |

Live check on 2026-11-08 (all five feeds read through the app's own readers): Remote OK 99 jobs, Remotive 12, Arbeitnow 300, Himalayas 20 (the first page only), We Work Remotely 25 (its RSS needed the fetcher to accept `application/rss+xml`, which it refused until this check). Against the four example searches, **India on-site or hybrid matched 0 of 456** (as expected: the feeds have no Indian on-site jobs), India remote about 100, Dubai (remote) about 100, Europe or USA remote about 140. Many remote jobs do not say where they can be done from; those are kept and shown as "remote (where from: not stated)", so an India search can still show a job that is really for another country.

Honest coverage today: followed company boards plus five feeds. Feeds are mostly remote, so **India on-site and hybrid coverage is thin until Adzuna or Jooble is added**. Most Indian mid-size employers post on Naukri, which cannot be read.

### 10.2 Searches (where and how you want to work)
Discover has "Where and how I search": each search is regions, cities (any spelling: Bangalore finds Bengaluru; "Delhi NCR" is five cities) and remote, hybrid or on site, with optional title words. A job is kept when it fits **any** enabled search. Examples built in as one-click presets: India on site or hybrid in big cities; India remote; Dubai on site or remote; Europe and USA remote. A remote job is kept for India only when it says India, APAC or worldwide, or says nothing about where from; "Remote - US" is rejected. A location the app cannot read is not matched (a missed job is better than a wrong city) and the run says how many were left out. The same searches filter the daily apply list.

### 10.3 Applying to 50 to 100 jobs a day: what is possible
- The app **cannot submit applications** (site terms, CAPTCHAs, every form differs, and the project rule: no submit action). It makes the list, the research and the order; **you** press apply. Time per application on a real site is 3 to 10 minutes (forms, uploads, questions), so 50 a day is about 4 hours and 100 about 8 hours. That is a hard limit of the approach, not of the app.
- Setting `daily_limit: 100` in the apply policy is allowed. Only the first `deep_limit` (default 10) are researched on the web (about 5 searches each); the rest are listed from what the post and your tracker say, and any can be researched with one click. This keeps 100 items to roughly 50 searches a day instead of 500.
- Honest advice: mass applying has a low reply rate; 20 to 30 targeted applications plus referrals usually beats 100 cold ones. The list ranks by match, so working from the top is the efficient order.

### 10.4 Keeping interview preparation current and ranked
- Research findings are merged across pages: the same question found on another page is not duplicated, it gains a mention and the extra source ("Asked on 3 pages"). The inbox is ordered by mentions, then closeness to the role.
- Every day, up to 3 jobs you are actually pursuing (shortlisted, applied, interviewing) that were not researched in the last 7 days get a new research run. This needs a model key and a search service; without them nothing runs and nothing is charged.
- Not built: ranking by how often *this company* asks it (needs interview-experience pages per company), and feeding your own mock-interview misses back into the order.

### 10.5 Cost for your usage (estimates, not measurements: no model key has ever been used here)
Assumptions: 100 jobs listed a day, 10 researched on the web, 100 job descriptions read, 10 jobs researched for interviews a week-day, 1 mock interview a day, 10 notes questions a day, 20 drafts a day. Token sizes are my estimates (a job description about 3,000 tokens in and 300 out; a researched page about 5,000 in and 1,000 out). Prices per million tokens, input / output: Haiku 5.5 $0.10 / $0.50, Sonnet 5.5 $2 / $10 (checked on Anthropic's page 2026-11-06).

| Task | Model | Per unit | Per day | Per month |
|---|---|---|---|---|
| Choosing and ranking the 100 daily jobs, pay and interview search | none (rules) | $0 | $0 | $0 |
| Web searches for 10 deep items (about 50) | SearXNG (free) | $0 | $0 | $0 (Tavily's free 1,000 a month covers about 6 deep items a day) |
| Reading 100 job descriptions | Haiku | $0.0005 | $0.05 | about $1.5 |
| Same on Sonnet | Sonnet | $0.01 | $1 | about $30 |
| Interview research for 10 jobs (12 pages each) | Haiku | $0.012 per job | $0.12 | about $4 |
| Weekly refresh of live applications (3 a day) | Haiku | $0.012 | $0.04 | about $1 |
| One mock interview (10 questions, graded) | Sonnet | about $0.09 | $0.09 | about $3 |
| 10 notes questions a day | Sonnet | $0.011 | $0.11 | about $3 |
| 20 outreach drafts a day | Haiku / Sonnet | $0.0005 / $0.008 | $0.01 / $0.16 | $0.3 / $5 |
| **Total, bulk on Haiku and judgement on Sonnet** |  |  | **about $0.4** | **about $12 to 15** |
| Total, everything on Sonnet |  |  | about $2 | about $60 to 80 |
| Total with DeepSeek V4 Flash for bulk (about $0.14 / $0.28) and Claude for judgement |  |  | about $0.3 | about $9 to 12 |

The daily token cap (`CAREERPILOT_LLM_DAILY_TOKEN_CAP`, default 200,000) stops a bad day: at Haiku prices that is at most about $0.10 a day, at Sonnet prices about $0.60 to $1. Add a prepaid top-up of $10 to $20 and a month is covered at this usage.

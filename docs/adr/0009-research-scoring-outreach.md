# 0009: Company research, scoring, outreach and interview intel

Status: accepted (2026-11-05). Part of Phase 4.

## The one rule behind all of it
The model may supply evidence or wording. **Code decides what is believed**, and every outward action is yours. Pages and job texts are written by strangers, so they are treated as data: they go to the model inside a `<tag>` block (`core/prompts.data_block`, which defuses a literal closing tag), and the model has no tools and no way to act. That removes the usual prompt-injection damage rather than hoping the model resists.

## The fetcher (`core/fetcher.py`)
The only code that fetches pages for research. Checked by 83 tests (the SSRF suite).
- http/https, ports 80 and 443 only, no credentials in the URL, no cookies, no environment proxies.
- The host is resolved **by us**; every address must be public (loopback, private, link-local, CGNAT, multicast, IPv4-mapped IPv6, NAT64 and 6to4 are refused). The request then connects to the address that was checked and keeps the real name for `Host` and TLS, so a name cannot answer differently a moment later (DNS rebinding).
- Redirects are followed by hand, up to 4, and each hop is checked again.
- The body is streamed and cut at 1 MB **after** decompression (compression bombs), with a 20 s deadline. Only text content types are read.
- LinkedIn, Indeed, Glassdoor and Naukri are refused (their terms forbid automation). Naukri is an addition to the plan's three.
- Not done yet, on purpose: robots.txt and per-host rate limits. Research fetches a handful of pages when you ask. Discovery (Phase 5) adds both.
- Third-party lookups send the company's domain to `rdap.org` (registration date) and `dns.google` (mail records). Both are public data.

## Company verification (`modules/verification`)
Eight checks and four hard red flags, stored per company (`company_checks`); the verdict is **computed** by `rules.compute_verdict`: 7-8 verified, 5-6 likely genuine, 3-4 needs check, otherwise suspicious; any raised flag forces suspicious.
- Code checks: site loads over HTTPS with a valid certificate, domain age (RDAP), mail records, careers page. A failed lookup is "unknown", never "fail".
- The model reads up to six of the company's own pages (fixed paths, so the model chooses no URLs) and judges registration, contact details and people. A pass or fail is kept only if its URL is a page it was shown, its quote is on that page (`core/evidence.quote_appears`), and the quote looks like the thing it claims (an identifier, an email or phone, a role). Independent mentions are never claimed by the model.
- Red flags (asks for money, chat-only hiring, no interview, free-mail recruiter) come from the job text with a quote, ignoring scam warnings ("we never ask for a fee"). They are raised automatically and cleared only by you.
- Your own findings are never overwritten by an automatic run. A quote you add is checked against the page you point to.
- **Known limit:** a quote proves the words are on the page, not that the page is honest. The UI says so and shows every quote. Replaced from the plan: no free-roaming agent loop, because fixed pages need no tools.

## Scoring (`modules/scoring`)
Six components with versioned weights (`SCORING_VERSION`): skills 30, pay 20, seniority 15, company 15, location and visa 10, growth 10. A component with too little information is left out and the rest re-weighted; `coverage` shows how much was measured. Skills come from `content/skills.yaml` (one vocabulary for jobs and your profile); your profile is `content/private/profile.yaml`. Growth and warning signs come from an optional model reading whose quotes are checked. The "chance" label is a **rule of thumb, not a probability**; a calibration view needs real outcomes (Phase 6).

## Outreach (`modules/outreach`)
Drafts (written by you or generated as two variants) are linted by `outreach/lint.py` (the old script, ported). States: draft, approved, sent, rejected; **no state or code path sends anything** (a test scans the routes and the source). "Sent" only records that you sent it yourself, and schedules a follow-up six days out. Approval requires: no unread lint flags, a recipient whose address has a published source (or a referral), a company not judged suspicious, one approved message per role and channel (a database index), and fewer than 10 approvals today. Facts given to the generator must be in the job text or on a page you name.

## Interview intel (`modules/intel`)
You paste text you read, or have a company page fetched; the model extracts rounds, topics, questions and tips, each with a quote that must be in the source. Reliability is a rule (recency 40, specific quote 20, other sources agreeing 40). A text about another company produces items marked **inferred** and ranked lower; the model only suggests which companies to read about and never writes facts about their interviews. Review sites are for you to paste, never to scrape.

## Prompts and cost
Prompts are files under `prompts/<name>/vN.md` (`core/prompts.py`); `llm_calls.purpose` records the version. `core/llm.call_llm_json` validates replies with one repair attempt, and every attempt counts against the daily token cap.

## Mock interviews (`modules/mock`)
The model plays the interviewer on a job (its description and any collected intel) or a topic: it asks one question, then for each answer returns a 0-5 score, short feedback and the next question in one call. Your answer goes to the model inside a data block, scores outside 0-5 are rejected and repaired, and your own notes are added as reference only when they cover the question. The summary (average, weak topics under 3, strong topics from 4) is computed by code, not by the model. A `turn` number in each answer makes a double submit a 409, and the session is re-read under a row lock after the model call (the call commits, which releases the lock). Transcripts are stored as JSON on the session. Scores are the model's opinion; the screen says so.

## Not built
An MCP tool for these features, a live Claude check (no key was available), Gmail drafts, and a task queue (research runs inside the request, a few seconds).

## Dependency
`httpx` is now a runtime dependency (it was a test-only transitive one): the fetcher uses it directly. Removal path: switch the fetcher to `httpx2`, which the Anthropic SDK already installs.

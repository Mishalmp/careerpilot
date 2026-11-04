# Interview Intel: how to collect it, and what to do when a company has no public data

Feeds the **Interview Intel** and **Company Intel** sheets and decides what you study for each company. Honest scope: this gives you topic hints and a process outline, not guaranteed questions.

## 1. Sources, ranked by reliability

| Rank | Source | Notes |
|---|---|---|
| 1 | The recruiter or hiring manager | Ask directly: "How many rounds, what does each cover, any prep you recommend?" Most reliable, and normal to ask. Record the answer in the sheet |
| 2 | The company's own pages | Engineering blog, "how we hire" or careers FAQ, job description wording (stack, level, responsibilities) |
| 3 | Employees and alumni | A short message to someone you know or a mutual connection; referrals double as intel |
| 4 | Public interview write-ups | GeeksforGeeks interview experiences, LeetCode Discuss, Reddit threads, personal blogs, YouTube. Quality varies; check dates |
| 5 | Review and Q&A sites | Glassdoor, AmbitionBox, Blind and similar. Their terms restrict automated scraping (Glassdoor's do), so read a page yourself and note the findings by hand; do not bulk-collect |

Treat anything older than about 12 to 18 months with caution; processes change.

## 2. Capture format (one row per company and role in Interview Intel)

Company, role, source type, similar-to (if inferred), source URL and date, rounds count, process summary (for example "recruiter call, online test, two technical, managerial, HR"), round details, topics tested, common questions reported (one per line, with source), difficulty, time to decision, confidence, prep notes.

Confidence rule (assumption): **High** = two or more independent, recent sources agree or the recruiter told you; **Medium** = one recent source; **Low** = old or single vague source. Mark inferred rows **Similar-company (inferred)**.

## 3. When the company has little or no public data (common for small Indian firms)

1. **Ask first** (recruiter), then the JD: its stack and level predict the round topics better than any review.
2. **Pick peers**: same type (product vs services vs startup), size, stage, domain and stack, and similar hiring bar. Example: for an early-stage fintech with a Python and React stack, use other early-stage Indian fintech and SaaS startups.
3. **Pull their intel** and record it under the target company as **Similar-company (inferred)**, naming the peers.
4. **Fall back to role-based defaults** from the guides in this folder: backend (Python, SQL, API design, system design basics), data engineering (SQL, pipelines, dbt, modelling), full-stack (JS or TS, React, API).
5. Prepare breadth first, then go deep on the JD's must-haves.

## 4. From intel to a prep plan

1. Tag every reported question or topic to a row in **Prep Topics**.
2. Count frequency across the company's rows (and peers); topics reported more than once rise to High.
3. Check your confidence scores; anything at 2 or lower and frequently reported goes to the top of the next day.
4. Build a **company brief** (one page): process, rounds, topics, three likely questions, three questions to ask, one specific reason you want to work there, two proof points from your projects.
5. Do one mock at the likely round format.

## 5. Typical process shapes (use as defaults, not facts about any company)

- **Indian product company:** recruiter call, online coding test, 2 to 3 technical rounds (DSA, then design or project), managerial, HR.
- **Startup:** founder or recruiter call, a take-home or live practical task, one or two technical conversations, culture or founder round.
- **Services or consultancies:** aptitude or basic technical screen, one or two technical interviews, HR.
- **Global remote company:** recruiter screen, a take-home or pairing, technical interview, values or cross-team interview, sometimes a trial period. Time-zone overlap and written communication are tested.

## 6. Interview-process red flags (also feeds company verification)
Offer without any interview; interviews only by chat apps; requests for money, deposits or "training fees"; asking for ID documents or bank details before an offer; vague company details, free email addresses, no way to verify the interviewer; pressure to accept within hours. Walk away and note it in Company Intel.

## 7. How the platform would automate this (later, optional)
An agent searches allowed sources per company, extracts rounds, topics and questions into the fixed schema with a source URL and quote for every field, re-reads each cited page to confirm it, scores reliability, and falls back to peers when evidence is thin. A person reviews before anything is trusted. See `job-hunt-decision-v2.md` section 4.

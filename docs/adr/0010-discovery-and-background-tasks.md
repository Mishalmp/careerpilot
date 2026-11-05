# 0010: Job-board discovery and background tasks

Status: accepted (2026-11-06). Part of Phase 5.

## Discovery (`modules/discovery`)
- **Three public boards only:** Greenhouse, Lever and Ashby, the endpoints companies publish for their own career pages. The header of `adapters.py` records what was checked (called on 2026-11-06; the providers' full terms were not re-read; not legal advice). One request per board per day, through the safe fetcher (ADR 0009), so a redirect to LinkedIn, Indeed, Glassdoor, Naukri or an internal address is refused. The board name is validated, so it cannot change the host.
- **An inbox, not an import.** A real board has hundreds of jobs (measured: Greenhouse 678, Lever 309, Ashby 71). Listings go to `discovered_jobs`; only the ones you accept reach the tracker. Re-reading a board adds only unseen listings, keeps accepted and dismissed ones as they are, and shows listings that left the board as "no longer on the board". Per-board title words (include / exclude) narrow what is kept.
- **No duplicates, twice over:** `(source, external id)` is unique, and accepting goes through the tracker's job fingerprint, so a job you already track is recognised and linked instead of copied.
- **Descriptions:** Lever and Ashby lists include them. Greenhouse's list does not (and with them it is megabytes), so its description is fetched when you accept.
- **Size:** board lists are read with an 8 MB limit; a larger board is refused with a message, never half-read.
- Not built: the Gmail job-alert parser (optional in the plan), discovery of boards themselves, scoring listings before you accept them.

## Background tasks (`modules/tasks`, `worker.py`)
- **A small Postgres queue instead of a library.** Needs: one user, two task kinds, idempotent scheduling, retry with backoff, a watchdog, and failures you can see. That is about 150 lines on the database we already have. The plan expected procrastinate (spike S3); I did not run that spike, so this is a choice made on size, not a measurement. If it needs many workers or priorities, replace `tasks/service.py`; handlers do not change.
- **Idempotent:** a task has a unique `(owner, key)` such as `discover:<source>:<day>`, so scheduling twice, or running two workers, queues once.
- **Safe to run in two places:** tasks are claimed with `FOR UPDATE SKIP LOCKED`; the claim is committed before the work starts.
- **Retries:** exponential backoff (1 minute doubling to 1 hour, plus up to 10 percent jitter), 3 attempts by default, then `failed` with the reason. A task stuck in `running` for 15 minutes (the worker died) is returned to the queue or failed. Unexpected exceptions are logged and shown as "see the server log"; their text is not stored, since it could contain secrets.
- **Visible and retryable:** the Tasks screen lists work with counts, errors and a Retry button (one or all failed).
- **Scheduler:** each pass queues today's reads for enabled boards after 07:00 local and the digest after 08:00 (settings). The worker runs inside the API process while it is up and can run alone with `python -m careerpilot.cli worker`. If the computer is off at 07:00, the run happens when the app next starts that day.
- A failure in one board never stops another: each is its own task.

## Daily digest (`modules/digest`)
A task builds one row per day: listings found in the last 24 hours and waiting, follow-ups due, applications per status, failed tasks. It is shown on the Discover screen and replaced, not duplicated, if built twice. It is never emailed or sent anywhere.

## Verified
Against the real Greenhouse (Anthropic), Ashby and Lever (Palantir) boards through the running API: first read added 204, 30 and 185 listings after title filters, a second read added 0; a nonexistent board failed with its reason shown on the source; accepting twice created one tracker job. The new screens were not exercised in a browser: the dev server could not be pointed at a new API in this session.

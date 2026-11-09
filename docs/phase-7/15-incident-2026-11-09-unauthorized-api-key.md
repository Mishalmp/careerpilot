# Incident: unknown API key spent about $24 on Opus (2026-11-09), redacted summary

Status: open with the provider. This page is the **public-safe summary**: no account names, addresses, key identifiers, request ids, IP addresses or payment details. The full evidence (screenshots, request ids, timeline, drafts to the provider) is kept **only** in the owner's git-ignored folder `resume-kit/anthropic-incident-2026-11-09/` (`15-incident-FULL-evidence.md`). Never copy that detail back into a tracked file.

## What happened

- A second API key, not created for this app, was created under the owner's console account on 2026-11-09 and spent about $24 on Opus models in a burst of roughly 15 minutes, taking the balance negative. The app's own key spent about $0.02 (Sonnet and Haiku only), which matched the app's own records.
- A card charge for a $100 credit purchase (plus tax) was attempted and declined by the bank while auto-reload was reported off.

## Proven from our side

1. **This app did not do it.** 19 recorded model calls, all Sonnet or Haiku, about $0.022 in total, equal to the console figure for the app's key.
2. **The code cannot call Opus.** No Opus model name exists in the source, settings or `.env.example`.
3. **The app was not running** during the burst; the laptop was off or asleep and offline.
4. **The app's key never reached the repo.** `.env` is git-ignored; a history scan finds no key.
5. **Request size and models in the console log** (10,000 to 443,000 input tokens, mixed Opus versions, 370-second outputs) look like a coding agent on a large codebase, not this app.

## Root cause found on 2026-11-10 (owner's mailbox, not this app)

- Someone was reading the owner's Gmail over IMAP with a script, from a foreign address, one minute after a sign-in link for the owner's Claude account arrived; the link emails and a bank decline notice were then found in Trash, which the owner had not done.
- The credential was a **Gmail app password from 2023** that had been committed by mistake in the settings file of **two public repositories** in 2023. It stayed readable in public git history for about three years. App passwords sign in without a second factor, so 2-step verification did not protect the mailbox.
- Anyone able to read the mailbox can request a sign-in link for the Claude account and open it. That likely explains how the unknown key was created without any unknown device appearing in the Google account.

## What was done and what is still the owner's

Done: the app passwords were deleted; the Gmail settings, filters, forwarding, delegates and linked apps were checked (clean apart from the app password); a complaint and an update were drafted for the provider.

Owner still to do (cannot be done by the app): change the Google password and sign out everywhere; make the two public repositories private (or purge them); rotate any other secret ever stored in those repositories; check the recovery mailbox the same way; change passwords on important services whose reset mail goes to the mailbox; set a monthly spend limit in the console and keep auto-reload off; delete unused keys; keep the card removed until the provider has answered.

## Protection to keep

- **Secrets never go in a tracked file, ever.** Use `.env` (git-ignored), keep `.env.example` for names only, and let the committed-secret test in `tests/test_hardening.py` run. A key committed once stays in history; rotate it, do not just delete the file.
- Turn on secret scanning on the GitHub repository, and keep it **private**.
- Console spend limit and a small prepaid balance cap what a stolen key can cost. The app's own dollar budgets (`CAREERPILOT_LLM_DAILY_BUDGET_USD`, `..._MONTHLY_BUDGET_USD`) only limit this app.
- Give the app its own workspace and key with its own small limit.
- Do not use app passwords at all; sign in with passkeys. If an old mail program needs one, replace the program.

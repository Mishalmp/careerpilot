# 0011: Backups, insights, offers and stories

Status: accepted (2026-11-06). Phase 6.

## Backups (`core/backup.py`)
- **What:** `pg_dump` in custom format, encrypted with AES-256-GCM, written as `backups/careerpilot-<time>.cpbk` (git-ignored). The newest 14 are kept. A nightly task runs it when a key is set (`CAREERPILOT_BACKUP_KEY`, made by `careerpilot backup-key`).
- **The key is yours, and only there.** It is not stored next to the backups, so a copied backup folder is unreadable. Lose the key and the backups are useless: keep it in a password manager.
- **Restore never overwrites.** `careerpilot restore FILE --into NAME` creates a new database and loads the backup into it; it refuses a name that exists, refuses the live database's name, and drops a half-restored copy if loading fails. A wrong key or a changed file stops before anything is created. To go live, point `CAREERPILOT_DATABASE_URL` at the new database.
- **Tool versions matter, and this was found by running it:** the `pg_dump` installed on this machine is version 17 and the database is 16, and its dump did not load back. So backup and restore refuse tools newer than the server, and `CAREERPILOT_PG_CONTAINER=careerpilot-postgres-1` runs the tools inside the Postgres container, which always matches.
- **Tested:** the test suite takes a backup of the test database, restores it into a fresh one, and compares the row count of every table, the vector extension and the migration version. It runs when matching tools or the container exist, and is skipped otherwise. The CLI was also run by hand: backup, restore, a second restore into the same name (refused), and a wrong key (refused, nothing created).
- **Dependency:** `cryptography` was already installed through the MCP SDK; it is now declared. Removal path: drop encryption and rely on disk encryption (BitLocker), which the threat model already assumes.
- Whole dump is held in memory while encrypting: fine at personal scale (the dev database dumps to 76 KB).
- Not done: shipping backups off the machine. Copy `backups/` somewhere else (another disk, cloud storage) yourself; they are encrypted.

## Insights (`modules/analytics`)
Read-only aggregator (like Today). **Funnel** from the status history: applied, heard back (interview or rejection), interviewed, offered, rejected, never answered, with rates as shares of applications and a warning under 10 applications. Weekly pace, 14 days of study minutes, topic progress, mock interview averages.
**Calibration:** for each fit label (good, possible, unlikely) how many scored jobs reached an interview, among applications whose outcome is known. Until 50 outcomes are known it says so and shows counts only. This is the honest way to answer "does the score work": with a small sample it cannot, and the screen says that rather than showing a percentage.

## Offer calculator (`modules/offers`)
Compares up to six offers in rupees per year: guaranteed pay, steady cash (fixed plus variable at the share you expect), first year (plus the joining bonus), equity kept apart as your own estimate, and how much is not guaranteed. Exchange rates are typed in by you with their date (one per currency; an old one is flagged after 90 days; a missing one leaves rupee figures empty). Nothing is fetched from the internet. Pre-tax only: tax rules are not modelled, and the screen says so. Notice period against the joining date they ask for is checked. Nothing about an offer is saved.

## STAR stories (`modules/stories`)
A bank of behavioural-interview stories with themes and an `evidence` field ("where is this written down"). Hints point at weak spots (very short parts, a number without evidence, "we" more than "I"); they never judge truth. A hint that tried to detect a missing outcome by word list was removed because it flagged good results.

## Deletion pass
Removed `tracker.repository.get_company` (unused) and unused web exports and type aliases found with `vulture` and `knip`; one duplicated `todayLocal` helper (four uses) became `lib/dates.ts`. Found by running: a CLI command registered under the wrong key since Phase 5 (`worker`), now covered by a test that parses every command.

## Not built
Google Sheets sync (optional in the plan), a referral CRM beyond the existing contact kind, and the server-side code runner, which the plan says needs a security review first.

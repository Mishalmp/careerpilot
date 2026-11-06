# Where these skills came from (read before updating or adding any)

Skills are instruction files an AI follows, so a bad one is a supply-chain and prompt-injection risk.
Rule for this repo: a skill is added only after a person (or Claude, with the owner's go-ahead) has
read **every file** in it, and it is pinned to the commit that was read. Never install from a
catalogue or "find a skill" tool without that review, and never at global scope (`~/.claude/skills`):
project scope only, so it cannot affect other projects on this machine.

| Skill | Source | Pinned commit | Licence | Reviewed |
|---|---|---|---|---|
| frontend-design | https://github.com/anthropics/skills (skills/frontend-design) | `ca45fc496a3436251f191354091d557da31c15b5` (2026-10-28) | LICENSE.txt in the folder | 2026-11-06: SKILL.md only; no scripts |
| webapp-testing | same repo (skills/webapp-testing) | same | LICENSE.txt in the folder | 2026-11-06: SKILL.md, `scripts/with_server.py` (starts a command you give it, waits for a local port), 3 example scripts (localhost only) |
| mcp-builder | same repo (skills/mcp-builder) | same | LICENSE.txt in the folder | 2026-11-06: SKILL.md, 5 reference guides, `scripts/evaluation.py` and `connections.py` (call the Anthropic API and an MCP server you point them at; **not run here**, need an API key) |

Reviewed for: network calls beyond localhost or the documented API, shell execution of fetched
content, reads of secrets or home-directory files, instructions that ask the model to hide actions,
ignore prior rules, or disable checks. None found. This is a human-readable review, not a guarantee.

## A tool that was considered and not installed
`fockus/claude-skill-find-skill` (single commit v1.0.1, 2026-04-21): a catalogue of about 4,800 skills
scraped from awesome-lists and a site map, plus an installer that `git clone`s any repository HEAD
into the agent's global skill folder and takes the "first match" in mono-repos. Its own code showed
no malware, but it automates exactly the unreviewed install this file forbids. Use it, if at all, as a
*search list* to find names, then review and pin as above.

# 02: Design system (look, feel, components, rules)

Covers REQ-01 to REQ-05. Tasks: group D (design system) and P (page redesigns) in `07-tasks.md`. Decision D1 (shadcn/ui + Radix + Tailwind), D5 (name and logo) are still **proposed**.

## 1. Honest note on the research
The reference products below were studied from their public documentation, blog posts and design write-ups (text only). I could not open and screenshot their live apps in this environment, so the "reverse engineering" is of their published design principles, not pixel measurements. If you send screenshots of any product you like (task Q03), I analyse them and adjust this file before D04. Colour values below are from memory of the Radix Colors scale and must be checked against radix-ui.com/colors in task D01; contrast ratios are checked by the script in D19.

## 2. References and what we take from each
| Product | What it is good at | What we take |
|---|---|---|
| Linear | Calm, dense, fast; one accent; theme generated from base colour, accent and contrast (LCH); Inter | Low-chroma neutrals, one blue accent, tight type scale, keyboard-first, no heavy shadows |
| shadcn/ui dashboards and blocks | The standard modern SaaS look: sidebar, cards, tables, command palette; semantic CSS variables; dark mode by `.dark` class | Component set, token names, sidebar layout |
| Radix Colors | 12-step scales with defined jobs per step, light and dark pairs, accessible text contrast | Our palette (blue + slate + status colours) |
| Huntr, Teal, Simplify, Careerflow (job-tracker products) | Kanban board, timeline per job, contacts, metrics, resume tools | Information layout for jobs: board + table views, job detail with timeline, status chips; we skip their resume builders |
| Vercel / Stripe dashboards (general SaaS) | Clear empty states, settings structure, status pages | Settings layout, status page, empty/error patterns |
| Anki / Duolingo-style learning apps | One question at a time, instant feedback, streaks | Quiz screen layout, feedback panel; no gamified noise |

## 3. Principles
1. **Calm and confident**: neutral surfaces, one blue accent, colour used for meaning (status, selection, primary action), not decoration.
2. **Density with air**: 14 px body, 8 px grid, readable tables; mobile gets larger touch targets.
3. **Consistent**: every screen is built from the same primitives; a screen that needs something new adds it to the system first.
4. **Fast feel**: skeletons instead of spinners for content, optimistic updates with rollback, keyboard shortcuts, command palette.
5. **Honest status**: errors say what happened and what to do; AI output is always labelled and linked to evidence.
6. **Accessible by default**: WCAG 2.2 AA, visible focus, keyboard complete, reduced motion respected, colour never the only signal.

## 4. Colour
**Palette source**: Radix Blue (accent), Radix Slate (neutral, cool gray that sits well with blue), Radix Green/Amber/Red (status). Step roles (Radix): 1-2 app and subtle backgrounds, 3-5 component backgrounds (normal/hover/active), 6-8 borders (subtle/normal/hover), 9 solid colour, 10 solid hover, 11 low-contrast text, 12 high-contrast text.

**Blue (light)**: 1 `#fbfdff`, 2 `#f4faff`, 3 `#e6f4fe`, 4 `#d5efff`, 5 `#c2e5ff`, 6 `#acd8fc`, 7 `#8ec8f6`, 8 `#5eb1ef`, 9 `#0090ff`, 10 `#0588f0`, 11 `#0d74ce`, 12 `#113264`.
**Blue (dark)**: 1 `#0d1520`, 2 `#111927`, 3 `#0d2847`, 4 `#003362`, 5 `#004074`, 6 `#104d87`, 7 `#205d9e`, 8 `#2870bd`, 9 `#0090ff`, 10 `#3b9eff`, 11 `#70b8ff`, 12 `#c2e6ff`.
**Slate (light)**: 1 `#fcfcfd`, 2 `#f9f9fb`, 3 `#f0f0f3`, 4 `#e8e8ec`, 5 `#e0e1e6`, 6 `#d9d9e0`, 7 `#cdced6`, 8 `#b9bbc6`, 9 `#8b8d98`, 10 `#80838d`, 11 `#60646c`, 12 `#1c2024`.
**Slate (dark)**: 1 `#111113`, 2 `#18191b`, 3 `#212225`, 4 `#272a2d`, 5 `#2e3135`, 6 `#363a3f`, 7 `#43484e`, 8 `#5a6169`, 9 `#696e77`, 10 `#777b84`, 11 `#b0b4ba`, 12 `#edeef0`.
Status colours use the same 12-step scheme for green (success), amber (warning), red (danger); the app uses steps 3, 6, 9, 11 of each.

**Semantic tokens** (CSS variables, shadcn-style names; values reference the steps; every component uses only these):
| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | slate 1 | slate 1 | page |
| `--surface` (card) | white | slate 2 | cards, panels |
| `--surface-muted` | slate 2 | slate 3 | table header, subtle blocks |
| `--border` | slate 6 | slate 6 | dividers, inputs |
| `--border-strong` | slate 8 | slate 8 | hover borders |
| `--foreground` | slate 12 | slate 12 | main text |
| `--muted-foreground` | slate 11 | slate 11 | secondary text |
| `--primary` | blue 9 | blue 9 | primary buttons, links on solid |
| `--primary-hover` | blue 10 | blue 10 | |
| `--primary-foreground` | white | white | text on primary (check contrast: blue 9 with white is about 3.4:1, which fails AA for small text, so primary buttons use blue 10/11 darker variant or bold 14 px+ text; decided at D01/D19 with a measured check) |
| `--accent-soft` | blue 3 | blue 3 | selected row, soft badge background |
| `--accent-text` | blue 11 | blue 11 | accent text and links |
| `--ring` | blue 8 | blue 8 | focus ring (2 px + 2 px offset) |
| `--success` / `--warning` / `--danger` | green 9 / amber 9 / red 9 | same | with `-soft` (step 3) and `-text` (step 11) variants |
| `--chart-1..5` | blue 9, slate 9, green 9, amber 9, violet 9 | same | charts (colour-blind check at D16) |
**Contrast gate (D19, first run during D01)**: a script computes WCAG contrast for every text/background token pair in both themes and fails below 4.5:1 (3:1 for large text and UI components). The primary button colour is decided by that script, not by eye.
**Rules**: no raw hex in components (lint rule); no gradients except the logo; no more than one accent colour on screen; status is colour + icon + text.

## 5. Theming mechanics
- Tokens defined in `apps/web/src/styles/tokens.css` on `:root` (light) and `.dark` (dark); Tailwind v4 `@theme inline` maps them to utilities.
- Modes: `light`, `dark`, `system` (default). Stored in `localStorage` (convenience only) and mirrored in a cookie so the server can render the right class and avoid a flash.
- No-flash: the root layout reads the cookie on the server and sets `class` on `<html>`; for `system` mode a tiny blocking script reads `prefers-color-scheme`. **CSP**: inline scripts are blocked by our CSP, so the script is either served as a same-origin static file loaded in `<head>` (preferred) or uses a per-request nonce. Decision at D05 after reading `apps/web/node_modules/next/dist/docs/` (Next.js version differs from older ones; CLAUDE.md rule).
- `color-scheme` set per theme so native controls and scrollbars match.
- Toggle: a three-state control (Light, Dark, System) in the user menu and the command palette.
- Images/diagrams that depend on theme use tokens (SVG `currentColor`/CSS variables), never baked colours.

## 6. Typography
Inter (variable, self-hosted via `next/font`, no external request) for UI; JetBrains Mono for code. Sizes: 12 (caption), 13 (table dense), 14 (body), 16 (lead), 20 (section title), 24 (page title), 32 (hero/empty). Line height 1.5 body, 1.25 titles. Weights 400, 500, 600. Numbers in tables use tabular figures. Max line length 72 characters for reading text.

## 7. Spacing, shape, elevation, motion
- 4 px base, scale 4/8/12/16/24/32/48. Page padding 24 (16 on phones). Card padding 16-20.
- Radius: 6 (inputs, buttons), 10 (cards), 999 (badges, avatars).
- Elevation: borders first, shadows only for floating layers (menus, dialogs): `0 8px 24px rgb(0 0 0 / 0.12)` light, with a border in dark.
- Motion: 120 ms for hover/press, 200 ms for panels/dialogs, ease-out; skeleton shimmer 1.2 s; all disabled under `prefers-reduced-motion`.

## 8. Icons and logo
**Icons**: Lucide (open source, consistent 24 px grid, 1.5 px stroke), imported per icon (tree-shaken). Sizes 16 (inline), 20 (nav), 24 (empty states). Decorative icons `aria-hidden`; icon-only buttons have `aria-label` and a tooltip.
**Logo**: name stays CareerPilot (D5, proposed). Mark: rounded square (radius 22%) in blue 9 with a white paper-plane glyph pointing up-right ("pilot" + progress). Wordmark: "CareerPilot" in Inter 600, "Career" in foreground, "Pilot" in blue 11. Assets in `docs/phase-7/assets/` (concept) and moved to `apps/web/public/` at D12 together with favicon (SVG + 32 px PNG + apple-touch 180 px) and an OG image. Mark must be legible at 16 px (checked at D12).

## 9. Layout
**App shell**: left sidebar (240 px, collapsible to 64 px icons; becomes a sheet on phones), top bar (breadcrumb, command palette trigger `Ctrl/Cmd+K`, theme toggle, user menu), content max width 1200 px with page header (title, description, actions). Sidebar groups: **Workspace** (Today, Jobs, Discover) · **Prepare** (Learn, Practice, Mock, Ask, Stories) · **Analyse** (Insights, Offers) · **System** (Architecture, Tasks, Settings). Badges show counts (reviews due, inbox items, failed tasks).
**Breakpoints**: 640 / 768 / 1024 / 1280. Tables become cards under 768 where needed. Touch targets 44 px on phones.
**Page header pattern**: title + one-line description + primary action right; tabs below when a page has views.

## 10. Components (primitive layer, then patterns)
**Primitives** (shadcn/Radix based, copied into `apps/web/src/components/ui/`): Button (primary, secondary, ghost, destructive, link; sizes; loading state), IconButton, Input, Textarea, Select, Combobox, Checkbox, Radio, Switch, Slider, Label/Field (with error and help), Badge/Chip, Avatar, Card, Tabs, Table (sticky header, sortable), Dialog, Sheet, Popover, Tooltip, DropdownMenu, ContextMenu, Command (palette), Toast, Alert/Banner, Progress, Skeleton, Separator, ScrollArea, Accordion, Breadcrumb, Pagination/Load more, Calendar/DatePicker.
**Patterns** (built from primitives, used by pages): AppShell, PageHeader, DataTable (filter bar, saved views, empty/loading/error states, keyboard row navigation), KanbanBoard (drag with keyboard alternative), Timeline, StatCard + Sparkline, EmptyState (icon, title, help, action), ErrorState (what happened, retry, details toggle), ConfirmDialog (names the thing, shows counts), FormSection with autosave indicator, SourceChip (link + date + reliability), AIBadge ("generated, checked: yes/no"), TaskProgress (live), MasteryRing, QuestionCard, DiagramCanvas (explorer), CodeBlock, MarkdownView (sanitised).
**Rules**: one component per file with a story-like entry on `/dev/ui` (development only) showing all states in both themes; props typed; no business logic inside primitives; no component imports a page.

## 11. States every screen must have (page checklist, repeated in `07`)
Loading (skeleton shaped like content) · Empty (what this is, how to fill it, primary action) · Error (message, retry, no stack trace) · Partial/stale (banner with time) · Offline (banner, writes disabled) · No permission/expired (redirect to login, return after) · Long content (truncate with expand) · Narrow screen · Both themes · Keyboard-only path · Reduced motion.

## 12. Forms and feedback
Validation on blur and on submit; messages next to the field in plain words; server errors (`problem+json` code) mapped to fields; unsaved-changes guard; submit disabled while pending with a spinner inside the button; destructive actions use ConfirmDialog; destructive but undoable actions use a toast with Undo for 8 s (soft delete, task B18). Toasts never hold the only copy of important information.

## 13. Data and state conventions (frontend)
Server data through TanStack Query; query keys `[resource, params]` from one helper; mutations invalidate by resource; optimistic updates only for toggles/status moves, with rollback and a toast on failure; UI state (filters, tabs) in the URL where shareable, else in component state; the generated OpenAPI client is the only way to call the API; no `fetch` in components.

## 14. Accessibility checklist (WCAG 2.2 AA, enforced by D19, T04 and the manual pass T20)
Contrast per section 4; focus visible (never `outline: none` without replacement); focus trapped in dialogs and returned on close; skip-to-content link; landmarks (`header`, `nav`, `main`); headings in order; form labels; error text linked with `aria-describedby`; live regions for toasts and task progress; drag-and-drop has keyboard alternative; target size >= 24x24 (44 on touch); no time limits except exams (which are announced and extendable in settings); `lang` set; reduced motion; zoom to 200% without loss.

## 15. Security in the UI
No `dangerouslySetInnerHTML` except through MarkdownView, which sanitises; links from stored/researched data pass the `Url` http(s) validation and render with `rel="noopener noreferrer"`; external-link icon shown; no secrets or tokens in client bundles or local storage; the pages have no CSP header yet (only the code-runner workers do; adding a page CSP is task H20); the theme script is a same-origin file so a strict CSP will still allow it; file inputs absent unless a task adds them with type/size checks.

## 16. Page-by-page design notes (detail in tasks P01-P17)
- **Today**: greeting line, 4 stat cards (applications active, interviews this week, reviews due, tasks needing attention), "Next best actions" list (rule-based), digest summary, upcoming (calendar-like list).
- **Jobs**: table (default) and board; filter bar with saved views; quick add (paste URL or text) in the header; row click opens a side sheet, full page for the timeline; status chips use soft colours + icon.
- **Job detail**: header (company, role, status stepper, fit score ring, check verdict), tabs: Overview, Timeline, Company check, Fit, Outreach, Interview prep (research + topics for this job), Notes.
- **Learn**: home with Today block, roadmap view (list with progress rings; graph later), topic page, quiz and exam focus modes (sidebar hidden, minimal chrome), inbox with bulk actions.
- **Practice**: problem list (filters), split editor/tests/output view, results with diff.
- **Ask**: chat-like single question box, answer with citation chips, "Not in your notes" state.
- **Insights/Offers/Stories**: charts follow the dataviz rules (one accent, direct labels, colour-blind safe); tables aligned right for numbers.
- **Architecture**: see `04`.
- **Tasks/Settings**: list with live status; settings in sections (Profile, Models and budgets, Search, Privacy, Backups, Appearance, Security).

## 17. Implementation order (see task ids)
Dependencies and tokens (D01-D05, fonts D06) → primitives and surfaces (D07-D09) → feedback conventions and command palette (D10-D11) → logo/favicon (D12) → app shell (D13) → icon map, status colours, charts, motion (D14-D17) → `/dev/ui` gallery, contrast script, visual regression (D18-D20) → owner review gate (D21) → usage doc (D22) → pages (P-group), starting with Jobs (P03), Today (P02) and Job detail (P05). Each page redesign is two tasks: structure with new components, then states and polish, each ending with the page checklist.

## 18. Verification
Contrast script (D19) · axe on every route in both themes (T04) · keyboard paths in each page's E2E test (T03) · screenshots at 3 widths in both themes compared to baselines (D20, T05) · owner review of the gallery (D21) before pages are redone.

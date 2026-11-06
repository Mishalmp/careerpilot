---
id: csp
title: Content Security Policy (CSP)
level: intermediate
related: [sessions-csrf, prompt-injection]
appears_in: [web]
proof: [apps/web/next.config.ts]
---


**Idea**: a response header that tells the browser which sources of scripts/styles/frames are allowed, limiting the damage of XSS. Inline scripts are blocked unless they carry a nonce or hash.

**In this app**: the pages currently send no CSP (adding one is H20); learner code runs in browser workers under their own CSP (ADR 0007); the theme-initialisation script must be compatible (D05).

**Fails**: loosening CSP for convenience (`unsafe-inline`), third-party scripts, new libraries needing `eval`.

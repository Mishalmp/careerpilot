---
id: ssrf
title: SSRF (server-side request forgery)
level: intermediate
related: [prompt-injection]
appears_in: [core:fetcher]
proof: [apps/api/tests/test_fetcher.py]
---


**Idea**: if the server fetches URLs a user supplies, an attacker can make it call internal addresses (cloud metadata, localhost, private ranges). Defence: resolve the host yourself, reject private/loopback/link-local/reserved ranges for every address, re-check on every redirect, cap size and time, allow only http(s).

**In this app**: everything that fetches goes through `core/fetcher.Fetcher`; research adds robots.txt and rate limits (R03). Blocked sites (LinkedIn, Indeed, Glassdoor, Naukri) are refused for terms-of-service reasons, not security.

**Fails**: DNS rebinding (name resolves to a public IP at check time and a private one at connect time: connect to the checked IP), IPv6 forms (`::ffff:127.0.0.1`), decimal/octal IP spellings, redirects to internal hosts, huge responses. H21 extends the tests.

**Interview**: "how do you build a link preview service safely".

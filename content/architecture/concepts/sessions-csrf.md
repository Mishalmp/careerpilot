---
id: sessions-csrf
title: Sessions, cookies and CSRF
level: beginner
related: [password-hashing, csp]
appears_in: [module:auth]
proof: [apps/api/tests/test_security.py, apps/api/tests/test_auth.py]
---


**Idea**: after you sign in, the server stores a session row and gives the browser an opaque id in a cookie. `HttpOnly` stops page scripts reading it; `SameSite=Lax` stops the browser sending it on most cross-site requests. CSRF (cross-site request forgery) is a site tricking your browser into sending a state-changing request with your cookie; the fix is a secret token the attacker's page cannot read, sent in a header on unsafe methods (POST, PATCH, DELETE).

**In this app**: the `Authenticated` dependency checks the session and the CSRF header together; `tests/test_security.py` walks every route and fails if one is unprotected.

**Fails**: a new route that reads the cookie by hand skips CSRF; a session never expires; the cookie lacks `Secure` over HTTPS.

**Interview**: "cookie vs token auth", "why SameSite is not enough alone", "where would you store a JWT and why (usually not localStorage)".

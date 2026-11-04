# 0003: Local security model

Status: accepted (2026-11-03)

## Context
The API listens on localhost, but any website open in the same browser can send requests to localhost, and DNS rebinding can make a hostile page look same-origin.

## Decision
- Single local user, created from the command line (`python -m careerpilot.cli create-user`); there is no sign-up endpoint.
- Password hashed with argon2. Unknown emails are verified against a dummy hash so timing and the error body do not reveal which emails exist.
- Server-side sessions: a random token in an HttpOnly, SameSite=Lax cookie; only the SHA-256 hash is stored.
- CSRF: every protected route depends on `current_session`, which requires the `X-CSRF-Token` header on any state-changing method. A hostile page cannot read the token or set the header.
- Origin check on all state-changing requests; Host header allow-list (`TrustedHostMiddleware`).
- The browser only talks to the Next.js app (port 3100); Next rewrites `/api/*` to the backend (port 8000). The cookie is same-origin and the API needs no CORS.
- Failed-login throttle is in memory (resets on restart; the owner can be locked out by anyone who can reach the API, acceptable on localhost).
- Validation errors drop the submitted value so passwords are never echoed or logged.

## Deferred
- A strict page-wide Content-Security-Policy with nonces. Decided in [0007](0007-practice-runner.md): not added yet; the code runner's workers get their own policies instead. The app sets frame, nosniff, referrer and permissions headers.
- TLS and a real identity provider, required before the app is ever exposed beyond localhost.

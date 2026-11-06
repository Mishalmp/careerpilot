---
id: password-hashing
title: Password hashing
level: beginner
related: [sessions-csrf]
appears_in: [module:auth]
proof: [apps/api/tests/test_auth.py]
---


**Idea**: store a slow, salted hash (argon2/bcrypt), never the password. Slowness makes guessing expensive. Rehash on login when parameters are raised.

**In this app**: check the hashing parameters in the users module (task B09 reviews them).

**Fails**: fast hashes (SHA-256), no salt, no throttle on guesses (our throttle is in memory today; B08 persists it).

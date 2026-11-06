---
id: backups
title: Backups and restore testing
level: intermediate
related: [migrations]
appears_in: [core:backup]
proof: [apps/api/tests/test_backup.py]
---


**Idea**: a backup you have not restored is a hope. Encrypt backups, keep the key apart, restore into a **new** database, compare row counts, rehearse.

**In this app**: `core/backup.py` (AES-256-GCM, version check against the server), restore never writes into the live database; scheduled restore drill (H10).

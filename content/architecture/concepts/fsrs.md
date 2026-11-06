---
id: fsrs
title: Spaced repetition and FSRS
level: intermediate
related: [idempotency]
appears_in: [module:learn]
proof: [apps/api/tests/test_learn_scheduler.py]
---


**Idea**: memory fades; reviewing just before you would forget is the efficient moment. FSRS models each card with **stability** (how long until recall drops to the target), **difficulty**, and **retrievability** (current recall probability), and schedules the next review for a target retention (we start at 90%). You grade each review Again/Hard/Good/Easy.

**In this app**: Python `fsrs` package (pinned) behind a scheduler interface (L08); rating from correctness, confidence and time (L09).

**Try it**: simulate answer patterns and see intervals.

**Fails**: too many new cards per day (reviews pile up; we cap), grading honesty (self-rated cards), changing parameters without migration.

---
id: sse
title: Server-sent events and progress
level: intermediate
related: [queues]
appears_in: []
proof: []
---


**Idea**: SSE is a one-way stream from server to browser over HTTP, with automatic reconnect and a `Last-Event-ID` header to resume. Good for progress (we only push server to client). WebSockets are two-way and heavier.

**In this app**: task progress events (B05); polling fallback if the stream is blocked.

**Fails**: proxies buffering the stream, auth on long-lived connections, missing resume so the page shows stale progress.

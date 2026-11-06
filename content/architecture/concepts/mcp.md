---
id: mcp
title: MCP (Model Context Protocol)
level: intermediate
related: [prompt-injection, agents-workflows]
appears_in: [mcp]
proof: [apps/api/tests/test_mcp_server.py]
---


**Idea**: an open protocol that lets an AI client (like Claude) discover and call **tools**, read **resources** and use **prompts** from a server, over stdio (local process) or HTTP. The server describes each tool with a name, description and typed input schema; the client's model decides when to call it. The newest spec revision we found (2026-07-28) moves toward stateless requests and optional extensions; we plan to align (H17).

**In this app**: the MCP server exposes tools that call services; writes **preview** until `confirm=true` and are audited; there is no send/delete/settings tool; user-facing problems use `ToolError`.

**Why those rules**: a tool result can contain injected text, and the model can be talked into misuse; so the dangerous actions simply do not exist, and writes need a second explicit step.

**Fails**: overly broad tools, vague descriptions (the model picks wrong tool), huge outputs, spec drift.

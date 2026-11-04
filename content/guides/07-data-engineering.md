# Data Engineering

Days 15 and 16. This is your strongest differentiator. Everything here maps to work you can describe from experience; keep claims within what your code does (see `12-project-defense-elphi.md` for limits).

## Core questions and short model answers

**1. ETL vs ELT.** ETL transforms before loading into the target; ELT loads raw data first and transforms inside the analytical engine. ELT suits cheap storage, scalable SQL engines and the need to reprocess raw history (your lakehouse: raw Delta, then dbt and DuckDB produce curated products).

**2. Lakehouse and medallion layers.** A lakehouse puts warehouse-like features (ACID tables, schema enforcement, time travel) on open files in object storage. Layers: raw/bronze (as received, append-only), cleaned/silver, curated/gold (business-ready data products). Your layout: raw Delta per object, curated product tables per account.

**3. Why Parquet?** Columnar, compressed, with column pruning and predicate pushdown. Good for analytics scans, poor for row-by-row updates. Watch the small-file problem; compact periodically.

**4. Delta Lake: what do you get?** A transaction log over Parquet files: ACID commits, optimistic concurrency (conflicting writers fail and retry), schema enforcement and evolution, time travel, `MERGE` upserts, `DELETE`, compaction (`OPTIMIZE`) and vacuum. Know that two writers to one table can conflict on commit; serialise or partition writers.

**5. DuckDB.** In-process columnar OLAP engine: fast SQL over Parquet and Arrow, no server. Good for single-node analytics and per-run transformations; not a multi-writer server database. Limits: memory and single machine; mind extension stability with very large file lists (reading Delta through the `deltalake` library into Arrow is one way to avoid pushing that into the engine).

**6. dbt.** SQL models with `ref()` dependencies, materialisations (view, table, incremental, ephemeral), tests (`not_null`, `unique`, relationships, accepted values, custom), sources and freshness, documentation and lineage. **Incremental models** process only new or changed rows using a unique key and a filter on a watermark; use `is_incremental()`. Be honest about how you used dbt (generated per run from YAML contracts) and for how long.

**7. Idempotency.** Running a job twice leaves the same final state. Techniques: upserts on a business key, replacing a partition or a scoped set of rows (delete-then-insert within a transaction or a Delta `replaceWhere`), deterministic output paths, deduplication keys, run identifiers. Test by running the same load twice and comparing counts.

**8. Deduplication.** Define a **functional key** (what makes a business row unique) and a version or timestamp. Keep the latest per key with `ROW_NUMBER() OVER (PARTITION BY key ORDER BY version DESC) = 1`, or compare against existing keys before appending. Decide how to treat the same key across snapshots (history vs latest).

**9. Incremental loading and watermarks.** Store the highest processed `updated_at` (or a change-feed position) per source; the next run asks for changes since then. Subtleties: clock skew, late updates (use an overlap window), deleted records (soft deletes or tombstones), source rate limits.

**10. Change data capture.** Log-based CDC (Debezium) vs query-based (watermark column) vs snapshot diffing. Trade-offs: completeness, source load, latency, delete handling.

**11. Late-arriving data and backfills.** Keep raw append-only so you can rebuild; support a date-range backfill parameter; make transformations deterministic; validate counts after a backfill; avoid double counting.

**12. Schema drift and contracts.** Sources change columns silently. Data contracts (declared schema, types, nullability, versioned with validity windows) validate at the boundary: fail loudly with the offending file or field rather than loading empty or wrong data. Version contracts so old data stays reproducible.

**13. Data modelling.** Star schema (facts and dimensions), grain, surrogate keys, slowly changing dimensions (Type 1 overwrite, Type 2 history), conformed dimensions, wide denormalised tables for reporting. Mapping rules in versioned YAML are your declarative model layer.

**14. Orchestration.** Orchestrators schedule, retry, parallelise, pause and resume, and alert (Kestra, Airflow). Concepts: DAGs or flows, task retries with backoff, SLAs, sensors and external triggers, backfills, idempotent tasks, secrets, per-tenant isolation. Explain how a paused flow resumes on a completion callback and what happens if the callback never arrives (known limit: manual resume).

**15. Data quality.** Tests at boundaries and after transforms (counts, nulls, uniqueness, referential integrity, accepted ranges), freshness checks, anomaly alerts, lineage. Quality is a pipeline feature, not a one-off audit.

**16. Failure handling in pipelines.** Retries with exponential backoff and jitter for transient errors; no retry for permanent errors (a 4xx payload problem fails identically); dead-letter handling for poison records; bounded retries; alerting; safe re-run through idempotency; checkpoints for long jobs. Be precise about what your system does and does not have.

**17. Performance and cost.** Partition by access pattern (date, tenant), prune columns, avoid small files, compact, push filters down, cache hot aggregates, right-size compute; measure before tuning.

**18. Multi-tenant data design.** Prefix per account in object storage, isolated tenant identity derived only from configuration, no account hard-coded in the engine, concurrency control per target table.

**19. Batch vs streaming.** Batch: simpler, cheaper, fine for daily or monthly finance data. Streaming (Kafka, Flink): needed for low latency; adds state, ordering and exactly-once complexity. Say why batch was the right fit for your problem.

## Practice
1. Whiteboard your pipeline: sources, raw, transform, product, callback, with failure points marked.
2. Write an incremental dbt model with a unique key and a late-data overlap window.
3. Implement dedup-latest-per-key in SQL and in pandas; test idempotency by running twice.
4. Explain a Delta `MERGE` and the concurrency conflict scenario.
5. Describe three schema-drift cases and what your contract does for each.

## Common mistakes
Saying "exactly-once" for a batch system without qualification; claiming checkpoint-resume you do not have; mixing up idempotent and deduplicated; no answer for late data.

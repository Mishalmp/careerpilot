# SQL and PostgreSQL

Days 2, 3, 5, 13. SQL is tested in almost every backend and data interview. Practice by typing queries, not reading them.

## Core questions and short model answers

**1. Joins.** INNER (matching rows), LEFT (all left plus matches), RIGHT, FULL, CROSS (all pairs), self-join. Anti-join: `LEFT JOIN ... WHERE right.id IS NULL` or `NOT EXISTS`. A filter on the right table in `WHERE` turns a LEFT JOIN into an inner join; put it in `ON`.

**2. NULL semantics.** `NULL = NULL` is unknown, not true; use `IS NULL`. Aggregates ignore NULLs except `COUNT(*)`. `NOT IN` with a NULL in the list returns nothing; prefer `NOT EXISTS`.

**3. `WHERE` vs `HAVING`.** `WHERE` filters rows before grouping; `HAVING` filters groups after aggregation. Logical order: FROM, WHERE, GROUP BY, HAVING, SELECT, DISTINCT, ORDER BY, LIMIT.

**4. Window functions.** Compute across related rows without collapsing them: `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `LAG`, `LEAD`, `SUM() OVER (PARTITION BY ... ORDER BY ...)`. Difference: `RANK` leaves gaps after ties, `DENSE_RANK` does not.

```sql
-- latest row per key (also the shape of "keep the latest version per functional key")
SELECT * FROM (
  SELECT t.*, ROW_NUMBER() OVER (PARTITION BY business_key ORDER BY updated_at DESC) AS rn
  FROM events t
) x WHERE rn = 1;

-- second highest salary
SELECT MAX(salary) FROM emp WHERE salary < (SELECT MAX(salary) FROM emp);

-- running total
SELECT day, SUM(amount) OVER (ORDER BY day) AS running FROM sales;
```

**5. CTEs.** Readability and reuse; recursive CTEs for hierarchies. In PostgreSQL 12 and later non-recursive CTEs can be inlined; do not assume they are optimisation fences.

**6. Indexes.** B-tree (default; equality and range), composite (leftmost-prefix rule), partial (index a subset), covering (`INCLUDE`), GIN (JSONB, arrays, full text). An index is not used when you wrap the column in a function (without a matching expression index), use a leading wildcard `LIKE '%x'`, mismatch types, or the planner expects to read most of the table. Indexes cost writes and space.

**7. `EXPLAIN ANALYZE`.** Read: scan type (Seq Scan, Index Scan, Bitmap), estimated vs actual rows (big gaps mean stale statistics, run `ANALYZE`), join type (Nested Loop, Hash, Merge), sort and spill to disk, time per node. Fix with an index, a rewritten predicate, better statistics, or less data earlier.

**8. Transactions and ACID.** Atomicity, Consistency, Isolation, Durability. PostgreSQL uses **MVCC**: readers do not block writers. Isolation levels: Read Committed (default), Repeatable Read, Serializable. Anomalies: dirty read, non-repeatable read, phantom, write skew. Deadlocks occur with opposite lock order; keep lock order consistent and transactions short.

**9. Locking and concurrency control.** `SELECT ... FOR UPDATE` locks rows; `SKIP LOCKED` powers job queues; advisory locks for application-level mutual exclusion (the single-flight pattern); optimistic concurrency with a version column.

**10. Idempotent upsert.** `INSERT ... ON CONFLICT (key) DO UPDATE SET ...` makes retries safe, given a unique constraint on the business key.

**11. Normalisation vs denormalisation.** 1NF to 3NF remove redundancy and update anomalies. Denormalise deliberately for read performance (reporting tables, data products), accepting duplication and the need to keep it consistent.

**12. Pagination.** `OFFSET` gets slower with depth and can skip or repeat rows when data changes. Keyset pagination (`WHERE (created_at, id) < (:last_created, :last_id) ORDER BY created_at DESC, id DESC LIMIT n`) stays fast and stable.

**13. Constraints and migrations.** Primary, foreign, unique, check, not null protect data at the source. Zero-downtime migrations: add nullable columns first, backfill in batches, add constraints `NOT VALID` then validate, create indexes `CONCURRENTLY`, deploy code that works with both schemas, then clean up.

**14. JSONB, partitioning, full-text search.** JSONB with GIN for semi-structured data (do not replace relational columns you query often). Declarative partitioning by range or list for large tables and cheap retention. Full-text: `tsvector` and `tsquery`.

**15. Gaps and islands, sessionisation, dedup.** Use `ROW_NUMBER` differences for consecutive groups; `LAG` with a time threshold for sessions; `ROW_NUMBER` or `DISTINCT ON` for dedup.

**16. OLTP vs OLAP.** Row stores and normalised schemas for transactions; columnar stores (Parquet, DuckDB, warehouses) for scans and aggregates. Your pipeline moves from the first world to the second.

## Practice (set a timer, 10 minutes each)
1. Top N per group; second highest; customers with no orders.
2. Month-over-month growth with `LAG`; running total and 7-day moving average.
3. Find duplicate emails and delete all but the latest.
4. Consecutive login streaks (gaps and islands).
5. Given a slow query and its `EXPLAIN` output, propose an index.
6. Write the keyset-pagination version of an `OFFSET` query.

## Where it connects
Per-tenant PostgreSQL databases, Alembic migrations across tenants, single-flight locks per job, consolidation-key dedup in ingestion, latest-version-per-key logic in transformations, DuckDB SQL generated by dbt.

## Common mistakes
Using `NOT IN` with NULLs; filtering the right side of a LEFT JOIN in `WHERE`; claiming an index always helps; forgetting that `OFFSET` paging is unstable.

## Practise in the editor

Solve these in the browser editor; your code runs in a sandbox and is checked against hidden tests.

- [Second highest salary](practice:second-highest-salary)
- [Duplicate emails](practice:duplicate-emails)
- [Customers without orders (anti-join)](practice:customers-without-orders)
- [Running total (window function)](practice:running-total)
- [Top two salaries per department](practice:top-two-salaries-per-department)
- [Longest login streak (gaps and islands)](practice:longest-login-streak)

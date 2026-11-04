# Python

Days 1, 2, 4, 6, plus daily refreshers. Say each answer aloud in under 90 seconds.

## Must-know checklist
Data model and mutability, scope and closures, iterators and generators, decorators, context managers, OOP and MRO, typing, GIL and concurrency, asyncio, memory management, exceptions, collections and complexity, pytest, packaging, performance.

## Core questions and short model answers

**1. Mutable vs immutable? The mutable default argument bug.**
Lists, dicts and sets are mutable; ints, strings, tuples and frozensets are not. A default `def f(x, items=[])` is evaluated once at definition, so every call shares the same list. Fix: `items=None`, then `items = [] if items is None else items`.

**2. `is` vs `==`.**
`is` compares identity (same object), `==` compares value via `__eq__`. Use `is` only for `None`, `True`, `False` and sentinels. Small-integer and string interning is an implementation detail; never rely on it.

**3. Shallow vs deep copy.**
`copy.copy` copies the container but shares nested objects; `copy.deepcopy` copies recursively (and handles cycles). Slicing a list is a shallow copy.

**4. How does a dict work? Why must keys be hashable?**
A hash table: the key's hash picks a slot, equality resolves collisions, average O(1) get and set. Insertion order is preserved from Python 3.7. A key's hash must not change while it is in the dict, hence immutable types.

**5. Iterator vs generator. Why use generators?**
An iterator implements `__iter__` and `__next__`. A generator function uses `yield` and creates an iterator automatically, keeping its local state between calls. They are lazy: one item at a time, constant memory, good for large files or streams (as in streaming rows through a pipeline).

**6. Write a decorator. Why `functools.wraps`?**
A decorator takes a function and returns a wrapper. `wraps` copies `__name__`, `__doc__` and annotations so tracebacks, docs and introspection stay correct. A decorator with arguments is a function that returns a decorator.

```python
import functools, time, random

def retry(times=3, base=0.5, exceptions=(Exception,)):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            for attempt in range(times):
                try:
                    return fn(*a, **kw)
                except exceptions:
                    if attempt == times - 1:
                        raise
                    time.sleep(base * 2 ** attempt + random.random() * 0.1)  # backoff with jitter
        return wrapper
    return deco
```

**7. Context managers.**
Objects with `__enter__` and `__exit__` (or `@contextlib.contextmanager` around a generator). They guarantee cleanup (files, locks, DB sessions, temporary directories). `__exit__` can suppress or propagate exceptions.

**8. What is the GIL? Consequences?**
In CPython, a lock that lets one thread execute Python bytecode at a time. CPU-bound Python threads do not run in parallel; I/O-bound threads do overlap because the GIL is released while waiting. For CPU-bound work use `multiprocessing` or native extensions (NumPy, pyarrow). Recent versions have an experimental free-threaded build; check current status before relying on it.

**9. Threads vs processes vs asyncio: when?**
I/O-bound with blocking libraries: threads. I/O-bound with async libraries and many connections: asyncio. CPU-bound: processes. Mixed: asyncio plus `asyncio.to_thread` or a process pool for blocking and CPU parts.

**10. How does asyncio work? What goes wrong?**
A single-threaded event loop runs coroutines cooperatively; `await` yields control. One blocking call (a sync DB driver, `time.sleep`, heavy CPU) stalls every request. Use async drivers, or move blocking work to `to_thread` or an executor. Use `asyncio.gather` or `TaskGroup` for concurrency; always handle cancellation and timeouts.

**11. MRO and `super()`.**
Method Resolution Order uses C3 linearisation: children before parents, left-to-right order preserved. `super()` follows the MRO of the instance, which matters in multiple inheritance. Inspect with `Class.__mro__`.

**12. `@staticmethod`, `@classmethod`, `@property`.**
Static: no implicit argument. Class method: receives the class (alternate constructors). Property: attribute access that calls a getter or setter, keeping a stable interface.

**13. Dataclasses vs plain classes vs Pydantic models.**
Dataclasses generate `__init__`, `__repr__`, `__eq__`; no runtime validation. Pydantic validates and coerces input, serialises to JSON; used at API boundaries. `__slots__` saves memory and blocks dynamic attributes.

**14. Late-binding closures.**
`[lambda: i for i in range(3)]` all return 2, since `i` is looked up at call time. Bind early with a default argument: `lambda i=i: i`.

**15. Memory management.**
Reference counting frees most objects immediately; a cyclic garbage collector handles reference cycles. `weakref` avoids keeping objects alive. Large data: prefer generators, `array`, NumPy or Arrow buffers.

**16. Exceptions.**
`try/except/else/finally`: `else` runs when no exception, `finally` always. Catch specific exceptions, never a bare `except:`. Chain with `raise NewError(...) from err`. Log with context and re-raise when you cannot recover.

**17. `*args`, `**kwargs`, keyword-only and positional-only.**
`def f(a, /, b, *, c)`: `a` positional-only, `b` either, `c` keyword-only. Use keyword-only for flags to avoid unreadable calls.

**18. Complexity cheat sheet.**
list: index O(1), append O(1) amortised, insert or delete at front O(n), `in` O(n). dict and set: average O(1). deque: O(1) at both ends. `heapq`: push and pop O(log n). Sorting O(n log n), Timsort is stable.

**19. `lru_cache` and when it bites.**
Memoises pure functions by hashable arguments. Danger: unbounded growth (use `maxsize`), caching methods keeps `self` alive, stale data for impure functions.

**20. Testing with pytest.**
Fixtures for setup and teardown and dependency injection, `parametrize` for cases, `monkeypatch` for env and attributes, mocks for external calls (`unittest.mock`). Test behaviour, not implementation; keep unit tests fast, and a few integration tests for DB and API.

**21. Packaging and environments.**
Virtual environments isolate dependencies; pin versions (lock file) for reproducible builds; separate dev and prod requirements; build Docker images from pinned dependencies.

## Practice tasks (do these with the clock running)
1. LRU cache with `OrderedDict` (O(1) get and put).
2. Retry decorator with exponential backoff and jitter (above), then add tests.
3. Flatten a nested list with a generator.
4. Group anagrams; top-K frequent words with `Counter` and `heapq`.
5. Producer and consumer with `asyncio.Queue`; add cancellation and a timeout.
6. A context manager that times a block and logs the duration.
7. Token-bucket rate limiter class with tests.

## Where this connects to your project
Generators for streaming rows through ingestion; retries with backoff in connector calls; asyncio and async SQLAlchemy in FastAPI; Pydantic at service boundaries; pytest around transformation SQL generation.

## Common mistakes in interviews
Explaining definitions without a consequence; confusing concurrency with parallelism; claiming asyncio makes CPU work faster; forgetting that a sync library call blocks the event loop.

## Practise in the editor

Solve these in the browser editor; your code runs in a sandbox and is checked against hidden tests.

- [Group anagrams (dict and sorting)](practice:group-anagrams)
- [Top K frequent (Counter)](practice:top-k-frequent)
- [Flatten a nested list (recursion)](practice:flatten-nested-list)
- [Two Sum](practice:two-sum)

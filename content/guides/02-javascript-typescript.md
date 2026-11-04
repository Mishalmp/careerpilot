# JavaScript and TypeScript

Days 17 and 18. Aim: explain the event loop and closures without notes, write the utility functions from memory, and use TypeScript types with confidence.

## Core questions and short model answers

**1. The event loop.**
JavaScript runs one call stack. Async work (timers, network, I/O) is handed to the host; callbacks queue up. After the stack empties, the loop drains the **microtask queue** (promise callbacks, `queueMicrotask`) completely, then takes one **macrotask** (timer, I/O callback), then repeats. So promise callbacks run before `setTimeout(..., 0)`.

```js
console.log(1);
setTimeout(() => console.log(2), 0);
Promise.resolve().then(() => console.log(3));
console.log(4);        // prints 1, 4, 3, 2
```

**2. Closures.** A function keeps access to variables of its defining scope after that scope ends. Uses: private state, factories, memoisation, callbacks. Classic bug: `var` in a loop shares one binding; `let` creates one per iteration.

**3. `this`.** Decided by how a function is called: method call (object before the dot), plain call (undefined in strict mode), `new`, or explicit `call`/`apply`/`bind`. Arrow functions have no own `this`; they capture it lexically.

**4. Prototypes and classes.** Objects delegate property lookup along the prototype chain. `class` is syntax over prototypes. Methods live on the prototype, shared by instances.

**5. Promises and async/await.** A promise is pending, fulfilled or rejected. `async` functions return promises; `await` pauses that function, not the thread. Errors: `try/catch` around `await`, or `.catch`. `Promise.all` fails fast; `allSettled` waits for all; `race` takes the first; `any` the first success. Forgetting `await` returns a promise instead of a value.

**6. `==` vs `===`; falsy values.** `===` no coercion. Falsy: `false, 0, -0, 0n, "", null, undefined, NaN`. Prefer `===`; use `??` (nullish) when `0` or `""` are valid values, `||` otherwise.

**7. `var`, `let`, `const`; hoisting; temporal dead zone.** `var` is function-scoped and hoisted with `undefined`; `let` and `const` are block-scoped and in the temporal dead zone until declared. `const` prevents rebinding, not mutation.

**8. Shallow vs deep copy.** Spread and `Object.assign` are shallow. `structuredClone` deep-copies most data (not functions). `JSON.parse(JSON.stringify())` loses dates, undefined and functions.

**9. Debounce vs throttle.** Debounce runs after calls stop for N ms (search box). Throttle runs at most once per N ms (scroll).

```js
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const throttle = (fn, ms) => { let last = 0; return (...a) => { const n = Date.now(); if (n - last >= ms) { last = n; fn(...a); } }; };
const memo = fn => { const c = new Map(); return x => c.has(x) ? c.get(x) : (c.set(x, fn(x)), c.get(x)); };
```

**10. Modules.** ES modules (`import`/`export`) are static, enabling tree-shaking; CommonJS (`require`) is dynamic. Know why a package may need transpiling.

**11. Browser basics.** Event bubbling and delegation, `localStorage` vs cookies vs `sessionStorage`, CORS (a browser rule enforced via headers from the server, not a server security feature), same-origin policy, XSS (escape output, CSP) and CSRF (tokens, SameSite).

**12. Performance basics.** Avoid layout thrash, batch DOM updates, lazy-load, code-split, cache with proper headers, measure with the browser profiler.

## TypeScript

**13. `type` vs `interface`.** Both describe shapes. Interfaces can merge declarations and extend neatly; types can express unions, intersections, mapped and conditional types. Pick one convention and stay consistent.

**14. `any` vs `unknown` vs `never`.** `any` switches checking off. `unknown` forces narrowing before use. `never` is the type of values that cannot occur (exhaustive checks).

**15. Narrowing.** `typeof`, `instanceof`, `in`, equality checks, user-defined type guards (`x is Foo`), and discriminated unions (a shared literal `kind` field).

**16. Generics.** Reusable typed code: `function first<T>(xs: T[]): T | undefined`. Constraints: `<T extends { id: string }>`.

**17. Utility types.** `Partial`, `Required`, `Readonly`, `Pick`, `Omit`, `Record`, `ReturnType`, `Parameters`, `Awaited`. Know one-line examples for each.

**18. Types vanish at runtime.** TypeScript checks at compile time only; validate untrusted data at runtime (Zod, Yup, Pydantic on the server).

## Practice
1. Predict outputs for 10 event-loop snippets (timers, promises, async/await).
2. Implement `debounce`, `throttle`, `memo`, `Promise.all`, `curry` from memory.
3. Convert a small JS module to TypeScript with discriminated unions and no `any`.
4. Explain a fetch with retry and timeout using `AbortController`.

## Where it connects
Typed API clients and Redux Toolkit slices in the Elphi frontend; Yup schemas next to TypeScript types; SSE or streaming reader utilities.

## Common mistakes
Saying JavaScript is "multi-threaded"; mixing up microtasks and macrotasks; believing `const` makes objects immutable; using `any` to silence errors.

## Practise in the editor

Solve these in the browser editor; your code runs in a sandbox and is checked against hidden tests.

- [Two Sum](practice:two-sum)
- [Group anagrams](practice:group-anagrams)
- [Flatten a nested list](practice:flatten-nested-list)
- [Merge intervals](practice:merge-intervals)

# React and Next.js

Days 19 and 20. Stack facts from your frontend: Next.js 16, React 19, TypeScript, Redux Toolkit, Tailwind, AG Grid and AG Charts, next-intl, Vitest.

## Core questions and short model answers

**1. How does React render? What is reconciliation?**
State or prop changes trigger a re-render of the component and its children. React builds a new element tree, compares it with the previous one (reconciliation), and applies the minimum DOM changes. **Keys** identify list items so React can reuse the right nodes; use stable ids, not array indexes, when items reorder.

**2. `useState` pitfalls.** Updates are batched and asynchronous. Use the functional form when the new value depends on the old one: `setCount(c => c + 1)`. State is replaced, not merged.

**3. `useEffect`.** Runs after render for side effects. The dependency array controls when. Always clean up (subscriptions, timers, fetch abort). Stale closures happen when an effect captures old values; list dependencies honestly instead of silencing the lint rule. Do not use effects to derive state that can be computed during render.

**4. `useMemo`, `useCallback`, `React.memo`.** Performance tools, not defaults. `memo` skips re-render if props are shallow-equal; `useCallback` keeps a function identity stable so `memo` children do not re-render; `useMemo` caches an expensive computation. Measure first. (Know that newer React tooling can auto-memoise; say you check the project setup.)

**5. `useRef`.** A mutable box that survives renders without triggering one. DOM access, timers, previous values.

**6. Custom hooks.** Extract stateful logic (`useDebounce`, `useFetch`). Hooks rules: only at the top level of components or other hooks.

**7. State management: local vs context vs Redux Toolkit vs server state.** Local state for UI details; context for rarely changing values (theme, locale); Redux Toolkit for large shared client state with predictable updates and devtools; **server state** (fetched data, caching, invalidation) is best handled by a data-fetching layer such as RTK Query or React Query rather than hand-rolled in Redux. Context re-renders every consumer on change, so avoid putting fast-changing state in it.

**8. Controlled vs uncontrolled inputs.** Controlled: React state is the source of truth. Uncontrolled: the DOM holds the value, read via ref. Forms with many fields: Formik or React Hook Form with a Yup or Zod schema.

**9. Performance for big lists and grids.** Virtualise (render only visible rows; AG Grid does this), paginate on the server, memoise row renderers, avoid inline object props, split bundles, lazy-load heavy charts.

**10. Error handling.** Error boundaries catch render errors in a subtree (class components or a library); handle async errors yourself.

## Next.js

**11. SSR vs SSG vs ISR vs CSR.** SSR: HTML per request, fresh but slower. SSG: HTML at build time, fastest, static. ISR: static pages regenerated in the background after a time or on demand. CSR: render in the browser after load. Choose by data freshness, personalisation and SEO. Dashboards behind login are usually dynamic or client-fetched.

**12. App Router, server and client components.** Server components render on the server, ship no component JS to the client, and can read data directly; client components (`"use client"`) handle interactivity, state and browser APIs. Push `"use client"` as far down the tree as possible.

**13. Data fetching and caching.** Fetch in server components, control caching and revalidation per request or route, use route handlers for API endpoints, and mutate with server actions or client calls followed by revalidation. Caching defaults have changed between versions; read the current docs for the version you use.

**14. Middleware.** Runs before a request completes: auth redirects, locale routing, headers. Keep it light.

**15. i18n (next-intl).** Locale in the route, message files per language (EN and FR in your project), server-side translations, number and date formatting by locale. Accessibility: semantic HTML, labels, focus order, contrast.

**16. Security in a Next.js app.** Do not expose secrets to the client (only `NEXT_PUBLIC_` variables are public); validate server inputs; keep tokens in HTTP-only cookies where possible; escape output; set a content security policy.

**17. Testing.** Vitest and React Testing Library: test what users see and do (queries by role and text), mock network at the boundary, keep a few end-to-end tests for critical flows.

## Practice
1. Build a debounced search with abort of stale requests.
2. Reproduce a stale-closure bug and fix it.
3. Build a paginated table with server-side sorting.
4. Explain, with a sketch, how one of your dashboards loads data and why it is rendered the way it is.

## Where it connects
Reporting dashboards (P&L, OPEX/COGS drill-down), import wizards with progress, real-time monitoring screens, bilingual UI, AG Grid performance.

## Common mistakes
Putting everything in global state; effects that fetch without cleanup; claiming `useMemo` is always faster; not knowing what runs on the server versus the client.

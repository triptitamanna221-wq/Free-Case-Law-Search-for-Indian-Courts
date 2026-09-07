# Semantic Search over Indian Case Law — Frontend

Next.js (App Router) search UI for the FastAPI + PostgreSQL + pgvector backend
in the repo root. Public, read-only, no auth.

## Setup

```bash
npm install
cp .env.example .env.local   # set API_BASE_URL, or NEXT_PUBLIC_USE_MOCK_DATA=true for demo mode
npm run dev                   # http://localhost:3000
```

`NEXT_PUBLIC_*` env vars are baked in at **build time**, not read at runtime —
if you change `.env.local` after `npm run build`, rebuild before `npm start`.

### Demo mode (no backend required)

Set `NEXT_PUBLIC_USE_MOCK_DATA=true` in `.env.local` to exercise the full UI
against realistic mock data with zero backend running. This is an explicit
opt-in, never a silent fallback: a real, reachable-but-failing backend still
shows the real error UI (network/timeout/5xx messages), it doesn't quietly
swap in fake results.

## Architecture

Browser → this app's own `/api/search` and `/api/judgments/[id]` routes
(server-side proxies, Node runtime) → the FastAPI backend at `API_BASE_URL`.
Not a direct browser→backend fetch. Two reasons: `API_BASE_URL` stays
server-only (no `NEXT_PUBLIC_` prefix, never reaches the client bundle), and
the backend needs no CORS configuration at all, since the browser only ever
talks to this same-origin app.

```
web/
  app/
    layout.tsx, page.tsx
    api/search/route.ts, api/judgments/[id]/route.ts   # backend proxies
  components/
    search-page.tsx        # orchestration: URL state, fetch, filters, panel
    search-box.tsx          # hero input + combobox suggestions
    search-suggestions.tsx  # recent (localStorage) + curated examples
    search-mode-toggle.tsx
    results-list.tsx        # skeletons, empty states, result stagger
    result-card.tsx         # badges, match path, relevance bar
    metadata-panel.tsx      # retrieval-path breakdown + court/date filters
    judgment-panel.tsx      # slide-out detail, collapsible sections
    header.tsx, footer.tsx, theme-toggle.tsx, theme-provider.tsx
    ui/                     # shadcn/ui components
  lib/
    api.ts                  # fetch wrapper, timeout/error handling, mock-mode switch
    parse-judgment.ts       # splits raw_text on its own headings
    use-recent-searches.ts  # localStorage-backed, via useSyncExternalStore
    types.ts, mock-data.ts, format.ts, search-params.ts, use-debounce.ts
```

## Design

Dark-first. The palette lives in `app/globals.css` under Tailwind v4's
`@theme` — there is **no `tailwind.config.ts`** in v4, and the theme
deliberately reuses shadcn's existing variable names (`--primary`, `--card`,
`--muted`…) so all fourteen components under `ui/` re-skin from one place
rather than needing per-component edits.

**Colour carries meaning, not decoration.** Three colours map to the three
retrieval outcomes and are used identically on the mode toggle, each result
card's badge and rail, and the breakdown bar:

| | Path |
|---|---|
| emerald | matched by both BM25 and vector search |
| gold | lexical/BM25 match only |
| blue | semantic/vector match only |

Some deliberate departures from a generic "premium UI" treatment:

- **No animation library.** Framer Motion was considered and skipped: the
  stagger, collapse and hover effects here are all achievable in CSS
  (`grid-template-rows: 0fr→1fr` animates a collapse to natural height, which
  `height: auto` cannot), and ~50KB of JS is a poor trade on a page whose
  Lighthouse performance is already constrained by a free-tier backend.
  Measured 79 with the CSS approach, against 47 for the earlier build.
- **The relevance bar is relative, not a confidence score.** RRF produces
  small unitless values (~0.016–0.03) that mean nothing in isolation, so the
  bar is scaled against the top result in the current set and the tooltip says
  so. Calling it "confidence" would imply a calibrated probability RRF doesn't
  produce.
- **Suggestions are labelled "Try these", not "Trending".** There's no
  analytics pipeline behind this app; presenting a hardcoded list as trending
  would be inventing usage data. Recent searches *are* real, stored per-browser
  in `localStorage`.
- **Judgment sections come from the document, not a classifier.** The API
  returns one `raw_text` blob, so `lib/parse-judgment.ts` splits on headings
  the corpus genuinely contains (`PETITIONER:`, `BENCH:`, `CITATION:`,
  `ACT:`…) and falls back to rendering the text whole when a judgment has
  none. It does not infer a Facts/Issue/Holding structure that nothing in the
  data supports.

Accessibility: the suggestions dropdown implements the combobox pattern
(`aria-expanded`/`aria-controls`/`aria-activedescendant`, arrow-key traversal
with wrap, Escape to dismiss); collapsed panel sections are `hidden`, so they
leave the tab order; and `prefers-reduced-motion` disables every transform and
looping animation.

## API contract

**This diverges from a literal `search_mode`/`total`/`search_mode_breakdown`/
`offset` request-response shape** in favor of what the real backend
(`app/schemas/search.py`, `app/api/routes/search.py` in the repo root)
actually implements. Rather than build against an imagined contract and have
nothing work, the backend was extended (a small, real change — see its git
history) to add a genuine `search_mode` that skips the BM25 or vector query
server-side, and the frontend derives everything else client-side from what
the backend actually returns:

```jsonc
// POST /api/search (proxies to backend POST /search)
// Request
{ "query": "arbitration clause", "search_mode": "hybrid" | "keyword" | "semantic", "limit": 20 }

// Response (backend's real SearchResponse)
{
  "query": "arbitration clause",
  "results": [
    {
      "judgment_id": 12345, "chunk_id": 98765,
      "title": "...", "court": "...", "decision_date": "2023-01-15",
      "snippet": "...", "fused_score": 0.87,
      "matched_keyword": true, "matched_semantic": false
    }
  ],
  "took_ms": 45.2
}
```

`lib/api.ts`'s `toSearchOutcome()` derives, client-side, what the backend
doesn't compute itself:
- **`total`**: the backend has no `COUNT` query — true server-side pagination
  isn't implemented. `total` is just `results.length`. "Load more" re-fetches
  with a larger `limit` rather than a real `offset`; documented here rather
  than faked as real pagination.
- **`search_mode_breakdown`**: computed by counting each result's
  `matched_keyword`/`matched_semantic` flags — more accurate than a
  server-side breakdown would be anyway, since it reflects the real per-result
  match reason rather than a separately-computed aggregate.

`GET /api/judgments/[id]` proxies straight through to the backend's
`GET /judgments/{id}` (`JudgmentDetail`), no adaptation needed.

## Testing

```bash
npm run test         # 39 unit tests: query validation, URL param round-tripping,
                      # breakdown derivation, formatting/highlighting helpers,
                      # judgment heading parsing
npx eslint .
npm run build         # also does the real strict-TypeScript check (see below)
```

Type-checking is `npm run build`, not a standalone `npx tsc --noEmit` — this
app uses Next's typed-routes feature (`LayoutProps<"/">` in `app/layout.tsx`),
whose declarations `next build`/`next dev` generate into `.next/types` before
anything can check against them. A bare `tsc --noEmit` run on a fresh
checkout (nothing in `.next` yet) fails on that missing type even though the
code is correct — caught by actually reproducing this repo's CI on a clean
clone, not assumed away.

Verified manually (real browser automation, not just unit tests) against a
production build in demo mode: page loads, debounced as-you-type search
renders results, clicking a result opens the detail panel with real content,
mode toggle works, the URL reflects shareable search state, zero console/page
errors, zero failed requests — on desktop and at iPhone 14 / Pixel 7 viewport
widths with no horizontal overflow.

### Lighthouse

Real audit against a local `next start` production build (this repo's own
sandbox — a shared/virtualized environment, not representative hardware):

| Category | Score |
|---|---|
| Accessibility | **100** — zero failing audits |
| Best practices | 96 |
| Performance | **79** (was 47 before the redesign) |

Dark-mode contrast was checked separately, since Lighthouse audits whichever
theme it renders and dark is the primary target here: sampled text/background
pairs measure 17.0:1 (hero), 15.6:1 (result title and badges) and 7.0:1
(snippet body), all clearing WCAG AA.

**Re-run Lighthouse against the deployed Vercel URL** for numbers that reflect
CDN and edge caching — these local ones aren't a substitute for that.

## Deployment

```bash
npm run build && npm run start   # port 3000
```

Deploys zero-config to Vercel (also fine on Netlify, or Render as a Node web
service). Two environment variables, set in the platform's dashboard —
**not** in a committed file, since `.gitignore` excludes `.env*`:

| Variable | Value | Read where |
|---|---|---|
| `API_BASE_URL` | `https://case-law-search-api.onrender.com` | Server-side, at request time, by `app/api/*/route.ts` |
| `NEXT_PUBLIC_USE_MOCK_DATA` | `false` | Client bundle, inlined at **build** time |

Two things that bite here:

- **`API_BASE_URL` has no `NEXT_PUBLIC_` prefix, and must not get one.** The
  browser never calls the backend directly; it calls this app's own
  same-origin `/api/*` routes, which proxy server-side. Setting
  `NEXT_PUBLIC_API_BASE_URL` instead does nothing — the proxy falls back to
  `http://localhost:8000` and every search fails in production.
- **`NEXT_PUBLIC_USE_MOCK_DATA` is baked in at build time**, not read at
  runtime. Changing it in the dashboard requires a redeploy to take effect.

Because the proxy keeps all browser traffic same-origin, the FastAPI backend
needs **no CORS configuration** for this frontend — `CORS_ORIGINS` can stay
unset unless something else calls the API directly from a browser.

### Vercel, step by step

1. [vercel.com](https://vercel.com) → **Add New → Project** → import this repo.
2. Set **Root Directory** to `web` — the repo root is the Python backend, and
   Vercel will otherwise fail to find a Next.js app.
3. Add the two environment variables above (Production scope at minimum).
4. Deploy. Verify with a query the seeded corpus actually contains, e.g.
   "constitutional validity of a statute", and confirm results are real
   judgments rather than the mock fixtures.

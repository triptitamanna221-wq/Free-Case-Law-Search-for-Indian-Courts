"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { SlidersHorizontal } from "lucide-react";

import { JudgmentPanel } from "@/components/judgment-panel";
import { MetadataPanel, type DateRange } from "@/components/metadata-panel";
import { ResultsList } from "@/components/results-list";
import { SearchBox } from "@/components/search-box";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ApiError, getJudgment, searchJudgments } from "@/lib/api";
import { useDebouncedValue } from "@/lib/use-debounce";
import { buildSearchParams, parseSearchState, validateQuery } from "@/lib/search-params";
import type { JudgmentDetail, SearchMode, SearchOutcome } from "@/lib/types";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;
const EMPTY_DATE_RANGE: DateRange = { from: "", to: "" };

type SearchStatus = "idle" | "loading" | "success" | "error";

export function SearchPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const initial = useMemo(() => parseSearchState(searchParams), [searchParams]);

  const [query, setQuery] = useState(initial.query);
  const [mode, setMode] = useState<SearchMode>(initial.mode);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [hasSearched, setHasSearched] = useState(false);
  const [outcome, setOutcome] = useState<SearchOutcome | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<ApiError["kind"] | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const [selectedCourts, setSelectedCourts] = useState<Set<string>>(new Set());
  const [dateRange, setDateRange] = useState<DateRange>(EMPTY_DATE_RANGE);

  const [filtersOpen, setFiltersOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedJudgmentId, setSelectedJudgmentId] = useState<number | null>(null);
  const [judgment, setJudgment] = useState<JudgmentDetail | null>(null);
  const [judgmentLoading, setJudgmentLoading] = useState(false);
  const [judgmentError, setJudgmentError] = useState<string | null>(null);

  const debouncedQuery = useDebouncedValue(query, DEBOUNCE_MS);
  // avoids the debounce effect re-running an identical search right after an
  // explicit Enter/button submit already ran it.
  const lastSearchedKey = useRef<string | null>(null);
  const requestId = useRef(0);

  const runSearch = useCallback(
    async (searchQuery: string, searchMode: SearchMode, searchLimit: number) => {
      const validation = validateQuery(searchQuery);
      if (!validation.valid) {
        setStatus("idle");
        setHasSearched(false);
        return;
      }

      const key = `${validation.normalized}|${searchMode}|${searchLimit}`;
      if (key === lastSearchedKey.current) return;
      lastSearchedKey.current = key;

      const thisRequest = ++requestId.current;
      const isLoadMore = searchLimit > PAGE_SIZE && outcome != null;
      setStatus(isLoadMore ? "success" : "loading");
      setIsLoadingMore(isLoadMore);
      setHasSearched(true);

      router.replace(
        `${pathname}?${buildSearchParams({ query: validation.normalized, mode: searchMode })}`,
        { scroll: false }
      );

      try {
        const result = await searchJudgments({
          query: validation.normalized,
          mode: searchMode,
          limit: searchLimit,
        });
        if (thisRequest !== requestId.current) return; // a newer search superseded this one
        setOutcome(result);
        setStatus("success");
        setErrorMessage(null);
        setErrorKind(null);
      } catch (err) {
        if (thisRequest !== requestId.current) return;
        const message = err instanceof ApiError ? err.message : "Something went wrong.";
        const kind = err instanceof ApiError ? err.kind : "network";
        setErrorMessage(message);
        setErrorKind(kind);
        setStatus("error");
      } finally {
        if (thisRequest === requestId.current) setIsLoadingMore(false);
      }
    },
    [router, pathname, outcome]
  );

  // debounced as-you-type search. This is a real async-I/O effect (a network
  // call reacting to a derived value changing), not derived state that could
  // be computed inline -- setLimit here is the intentional "reset paging on a
  // new query/mode" side effect, not a lint-flagged render-time calculation.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLimit(PAGE_SIZE);
    void runSearch(debouncedQuery, mode, PAGE_SIZE);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery, mode]);

  const handleSubmit = useCallback(() => {
    setLimit(PAGE_SIZE);
    void runSearch(query, mode, PAGE_SIZE);
  }, [query, mode, runSearch]);

  const handleLoadMore = useCallback(() => {
    const nextLimit = limit + PAGE_SIZE;
    setLimit(nextLimit);
    void runSearch(query, mode, nextLimit);
  }, [query, mode, limit, runSearch]);

  const handleRetry = useCallback(() => {
    lastSearchedKey.current = null;
    void runSearch(query, mode, limit);
  }, [query, mode, limit, runSearch]);

  const handleSelectResult = useCallback((judgmentId: number) => {
    setSelectedJudgmentId(judgmentId);
    setPanelOpen(true);
  }, []);

  // fetches judgment detail when the panel opens on a new id -- another
  // legitimate async-I/O effect (see comment on the search effect above).
  useEffect(() => {
    if (selectedJudgmentId == null || !panelOpen) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setJudgmentLoading(true);
    setJudgmentError(null);
    setJudgment(null);
    getJudgment(selectedJudgmentId)
      .then((detail) => {
        if (!cancelled) setJudgment(detail);
      })
      .catch((err) => {
        if (cancelled) return;
        setJudgmentError(err instanceof ApiError ? err.message : "Could not load this judgment.");
      })
      .finally(() => {
        if (!cancelled) setJudgmentLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedJudgmentId, panelOpen]);

  const availableCourts = useMemo(() => {
    const courts = new Set<string>();
    for (const r of outcome?.results ?? []) {
      if (r.court) courts.add(r.court);
    }
    return Array.from(courts).sort();
  }, [outcome]);

  const toggleCourt = useCallback((court: string) => {
    setSelectedCourts((prev) => {
      const next = new Set(prev);
      if (next.has(court)) next.delete(court);
      else next.add(court);
      return next;
    });
  }, []);

  const filteredResults = useMemo(() => {
    const results = outcome?.results ?? [];
    return results.filter((r) => {
      if (selectedCourts.size > 0 && (!r.court || !selectedCourts.has(r.court))) return false;
      if (dateRange.from && (!r.decision_date || r.decision_date < dateRange.from)) return false;
      if (dateRange.to && (!r.decision_date || r.decision_date > dateRange.to)) return false;
      return true;
    });
  }, [outcome, selectedCourts, dateRange]);

  const activeFilterCount = selectedCourts.size + (dateRange.from ? 1 : 0) + (dateRange.to ? 1 : 0);

  const metadataPanel = (
    <MetadataPanel
      total={outcome?.total ?? 0}
      latencyMs={outcome?.latencyMs ?? null}
      breakdown={outcome?.breakdown ?? { keywordOnly: 0, semanticOnly: 0, hybrid: 0 }}
      availableCourts={availableCourts}
      selectedCourts={selectedCourts}
      onToggleCourt={toggleCourt}
      dateRange={dateRange}
      onDateRangeChange={setDateRange}
    />
  );

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6">
      <SearchBox
        query={query}
        mode={mode}
        isLoading={status === "loading"}
        onQueryChange={setQuery}
        onModeChange={(next) => {
          setMode(next);
          lastSearchedKey.current = null;
        }}
        onSubmit={handleSubmit}
      />

      <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-5 lg:gap-8">
        <div className="lg:col-span-3">
          {/* On narrow screens the stats/filters panel would push results far
              below the fold, so it moves into a bottom sheet behind this
              trigger. The same component instance renders in both places. */}
          {hasSearched ? (
            <div className="mb-4 flex items-center justify-between gap-3 lg:hidden">
              <p className="text-sm text-muted-foreground">
                {filteredResults.length.toLocaleString()}{" "}
                {filteredResults.length === 1 ? "result" : "results"}
              </p>
              <Button variant="outline" size="sm" onClick={() => setFiltersOpen(true)}>
                <SlidersHorizontal className="h-4 w-4" aria-hidden />
                Filters
                {activeFilterCount > 0 ? (
                  <span className="ml-0.5 rounded-full bg-primary px-1.5 text-[11px] leading-5 text-primary-foreground tabular-nums">
                    {activeFilterCount}
                  </span>
                ) : null}
              </Button>
            </div>
          ) : null}

          {/* Names the results region for screen readers and, just as
              importantly, supplies the h2 between the page h1 and the h3 on
              each result card -- without it the heading order skips a level,
              which Lighthouse flags as a real WCAG 1.3.1 failure. */}
          <h2 className="sr-only">Search results</h2>
          <ResultsList
            results={filteredResults}
            query={debouncedQuery}
            status={status}
            errorMessage={errorMessage}
            errorKind={errorKind}
            hasSearched={hasSearched}
            canLoadMore={status === "success" && (outcome?.results.length ?? 0) >= limit}
            isLoadingMore={isLoadingMore}
            onSelectResult={handleSelectResult}
            onRetry={handleRetry}
            onLoadMore={handleLoadMore}
          />
        </div>

        <aside className="hidden lg:col-span-2 lg:block">
          <div className="sticky top-20">{metadataPanel}</div>
        </aside>
      </div>

      <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
        <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto lg:hidden">
          <SheetHeader className="pb-2">
            <SheetTitle>Search details &amp; filters</SheetTitle>
          </SheetHeader>
          <div className="px-4 pb-6">{metadataPanel}</div>
        </SheetContent>
      </Sheet>

      <JudgmentPanel
        open={panelOpen}
        onOpenChange={setPanelOpen}
        judgment={judgment}
        isLoading={judgmentLoading}
        errorMessage={judgmentError}
      />
    </div>
  );
}

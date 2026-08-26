"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { JudgmentPanel } from "@/components/judgment-panel";
import { MetadataPanel, type DateRange } from "@/components/metadata-panel";
import { ResultsList } from "@/components/results-list";
import { SearchBox } from "@/components/search-box";
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

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
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

      <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-5">
        <div className="lg:col-span-3">
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
        <div className="lg:col-span-2">
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
        </div>
      </div>

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

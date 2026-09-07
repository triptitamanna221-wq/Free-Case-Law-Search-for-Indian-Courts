"use client";

import { FileSearch, Loader2, ScanSearch, SearchX } from "lucide-react";

import { ResultCard } from "@/components/result-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { ApiErrorKind } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

export function ResultsList({
  results,
  query,
  status,
  errorMessage,
  errorKind,
  hasSearched,
  canLoadMore,
  isLoadingMore,
  onSelectResult,
  onRetry,
  onLoadMore,
}: {
  results: SearchResult[];
  query: string;
  status: "idle" | "loading" | "success" | "error";
  errorMessage: string | null;
  errorKind: ApiErrorKind | null;
  hasSearched: boolean;
  canLoadMore: boolean;
  isLoadingMore: boolean;
  onSelectResult: (judgmentId: number) => void;
  onRetry: () => void;
  onLoadMore: () => void;
}) {
  if (status === "loading") return <ResultsSkeleton />;

  if (status === "error") {
    return (
      <Alert variant="destructive">
        <AlertTitle>Search failed</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-3">
          <span>{errorMessage}</span>
          {errorKind === "timeout" || errorKind === "network" || errorKind === "server" ? (
            <Button size="sm" variant="outline" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </AlertDescription>
      </Alert>
    );
  }

  if (!hasSearched) {
    return (
      <EmptyState
        icon={<ScanSearch className="h-6 w-6" aria-hidden />}
        title="Start with a question, not keywords"
        body="Describe the situation in plain language. The semantic path can match a judgment that shares no vocabulary with your query at all."
      />
    );
  }

  if (results.length === 0) {
    return (
      <EmptyState
        icon={<SearchX className="h-6 w-6" aria-hidden />}
        title="No judgments matched"
        body="The live demo is seeded with a 100-judgment sample rather than the full corpus, so gaps are expected. Try broader wording, or switch the mode above — semantic search often finds what keyword search misses."
      />
    );
  }

  // Bars are scaled against the strongest result currently shown, so the
  // comparison stays meaningful after client-side court/date filtering.
  const topScore = Math.max(...results.map((r) => r.fused_score));

  return (
    <div className="flex flex-col gap-3">
      {results.map((result, index) => (
        <ResultCard
          key={`${result.judgment_id}-${result.chunk_id}`}
          result={result}
          query={query}
          topScore={topScore}
          index={index}
          onSelect={onSelectResult}
        />
      ))}

      {canLoadMore ? (
        <div className="flex justify-center pt-3">
          <Button variant="outline" onClick={onLoadMore} disabled={isLoadingMore}>
            {isLoadingMore ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Loading…
              </>
            ) : (
              "Load more results"
            )}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/** Skeleton rows mirroring the real card's shape, so the layout doesn't jump
 *  when results replace them. */
function ResultsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
      <p className="sr-only">Searching judgments…</p>
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          style={{ animationDelay: `${i * 60}ms` }}
          className="animate-fade-up rounded-xl border bg-card p-5"
        >
          <div className="shimmer h-4 w-3/4 rounded bg-secondary" />
          <div className="mt-3 flex gap-1.5">
            <div className="shimmer h-6 w-32 rounded-md bg-secondary" />
            <div className="shimmer h-6 w-28 rounded-md bg-secondary" />
          </div>
          <div className="mt-3 space-y-2">
            <div className="shimmer h-3 w-full rounded bg-secondary" />
            <div className="shimmer h-3 w-11/12 rounded bg-secondary" />
            <div className="shimmer h-3 w-4/6 rounded bg-secondary" />
          </div>
          <div className="shimmer mt-4 h-1 w-24 rounded-full bg-secondary" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="animate-fade-up flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-14 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-muted-foreground">
        {icon}
      </span>
      <h3 className="font-medium">{title}</h3>
      <p className="max-w-sm text-sm text-balance text-muted-foreground">{body}</p>
      <FileSearch className="mt-1 h-4 w-4 text-muted-foreground/40" aria-hidden />
    </div>
  );
}

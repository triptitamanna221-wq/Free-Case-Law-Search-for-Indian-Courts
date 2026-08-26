"use client";

import { Loader2 } from "lucide-react";

import { ResultCard } from "@/components/result-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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
  if (status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-live="polite">
        <p className="sr-only">Searching...</p>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2 rounded-lg border p-4">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
          </div>
        ))}
      </div>
    );
  }

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
      <p className="py-12 text-center text-sm text-muted-foreground">
        Search real Indian court judgments by keyword, meaning, or both.
      </p>
    );
  }

  if (results.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No judgments matched your query. Try different terms.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {results.map((result) => (
        <ResultCard
          key={`${result.judgment_id}-${result.chunk_id}`}
          result={result}
          query={query}
          onSelect={onSelectResult}
        />
      ))}
      {canLoadMore ? (
        <div className="flex justify-center pt-2">
          <Button variant="outline" onClick={onLoadMore} disabled={isLoadingMore}>
            {isLoadingMore ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Loading...
              </>
            ) : (
              "Load more"
            )}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

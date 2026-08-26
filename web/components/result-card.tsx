"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatDate, highlightTerms, matchLabel, truncateWords } from "@/lib/format";
import type { SearchResult } from "@/lib/types";

const SNIPPET_WORD_LIMIT = 100;

export function ResultCard({
  result,
  query,
  onSelect,
}: {
  result: SearchResult;
  query: string;
  onSelect: (judgmentId: number) => void;
}) {
  const snippet = truncateWords(result.snippet, SNIPPET_WORD_LIMIT);
  const parts = highlightTerms(snippet, query);
  const label = matchLabel(result.matched_keyword, result.matched_semantic);

  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={() => onSelect(result.judgment_id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(result.judgment_id);
        }
      }}
      className="cursor-pointer transition-colors hover:bg-accent/50 focus-visible:ring-2 focus-visible:ring-ring"
    >
      <CardHeader className="gap-1">
        <h3 className="font-medium leading-snug">{result.title}</h3>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
          <span>{result.court ?? "Court unknown"}</span>
          <span aria-hidden>·</span>
          <span>{formatDate(result.decision_date)}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {parts.map((part, i) =>
            part.highlight ? (
              <mark key={i} className="rounded bg-yellow-200 px-0.5 text-foreground dark:bg-yellow-900">
                {part.text}
              </mark>
            ) : (
              <span key={i}>{part.text}</span>
            )
          )}
        </p>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">Score: {result.fused_score.toFixed(2)}</Badge>
          <Badge variant="outline">Match: {label}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

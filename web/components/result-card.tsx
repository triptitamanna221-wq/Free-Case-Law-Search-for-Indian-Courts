"use client";

import { ArrowUpRight, Building2, CalendarDays } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatDate, highlightTerms, matchLabel, truncateWords } from "@/lib/format";
import type { SearchResult } from "@/lib/types";

const SNIPPET_WORD_LIMIT = 90;

/** Colour carries the retrieval path, consistently across badge and bar:
 *  gold = lexical/BM25, blue = vector similarity, emerald = both. */
function matchTone(matchedKeyword: boolean, matchedSemantic: boolean) {
  if (matchedKeyword && matchedSemantic) {
    return { dot: "bg-both", text: "text-both", ring: "ring-both/25", bar: "bg-both" };
  }
  if (matchedKeyword) {
    return { dot: "bg-keyword", text: "text-keyword", ring: "ring-keyword/25", bar: "bg-keyword" };
  }
  return { dot: "bg-semantic", text: "text-semantic", ring: "ring-semantic/25", bar: "bg-semantic" };
}

export function ResultCard({
  result,
  query,
  topScore,
  index,
  onSelect,
}: {
  result: SearchResult;
  query: string;
  /** Highest fused score in the current result set, used to scale the bar. */
  topScore: number;
  index: number;
  onSelect: (judgmentId: number) => void;
}) {
  const snippet = truncateWords(result.snippet, SNIPPET_WORD_LIMIT);
  const parts = highlightTerms(snippet, query);
  const label = matchLabel(result.matched_keyword, result.matched_semantic);
  const tone = matchTone(result.matched_keyword, result.matched_semantic);

  // RRF scores are tiny and unitless (~0.016–0.03), so the raw number means
  // nothing to a reader. This is explicitly *relative* strength within the
  // current result set -- deliberately not called confidence, which would
  // imply a calibrated probability RRF doesn't produce.
  const relative = topScore > 0 ? Math.max(0.06, result.fused_score / topScore) : 0;

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
      style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
      className="group animate-fade-up relative cursor-pointer gap-0 overflow-hidden p-0 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-lg hover:shadow-primary/5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {/* rail echoing the match colour, so the path is scannable down the list */}
      <span className={`absolute inset-y-0 left-0 w-0.5 ${tone.bar} opacity-60`} aria-hidden />

      <div className="flex flex-col gap-3 p-4 pl-5 sm:p-5 sm:pl-6">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-serif text-base leading-snug font-semibold tracking-tight text-balance group-hover:text-primary">
            {result.title}
          </h3>
          <ArrowUpRight
            className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
            aria-hidden
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1.5 rounded-md bg-secondary px-2 py-1 text-xs text-secondary-foreground">
            <Building2 className="h-3 w-3 text-muted-foreground" aria-hidden />
            {result.court ?? "Court unknown"}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-secondary px-2 py-1 text-xs text-secondary-foreground">
            <CalendarDays className="h-3 w-3 text-muted-foreground" aria-hidden />
            {formatDate(result.decision_date)}
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs ring-1 ring-inset ${tone.ring} ${tone.text}`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} aria-hidden />
            {label}
          </span>
        </div>

        <p className="text-sm leading-relaxed text-muted-foreground">
          {parts.map((part, i) =>
            part.highlight ? (
              <mark
                key={i}
                className="rounded-sm bg-keyword/20 px-0.5 font-medium text-foreground"
              >
                {part.text}
              </mark>
            ) : (
              <span key={i}>{part.text}</span>
            )
          )}
        </p>

        <Tooltip>
          <TooltipTrigger
            render={
              <div className="flex items-center gap-2.5 pt-0.5" aria-label={`Relevance ${label}`} />
            }
          >
            <div className="h-1 w-24 overflow-hidden rounded-full bg-secondary">
              <div
                className={`h-full rounded-full ${tone.bar} transition-[width] duration-500`}
                style={{ width: `${Math.round(relative * 100)}%` }}
              />
            </div>
            <span className="text-[11px] tracking-wide text-muted-foreground tabular-nums">
              relevance
            </span>
          </TooltipTrigger>
          <TooltipContent>
            Reciprocal rank fusion score {result.fused_score.toFixed(4)}, shown relative to the top
            result. Not a confidence value.
          </TooltipContent>
        </Tooltip>
      </div>
    </Card>
  );
}

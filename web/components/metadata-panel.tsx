"use client";

import { Gauge, RotateCcw, SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import type { SearchModeBreakdown } from "@/lib/types";

export interface DateRange {
  from: string;
  to: string;
}

export function MetadataPanel({
  total,
  latencyMs,
  breakdown,
  availableCourts,
  selectedCourts,
  onToggleCourt,
  dateRange,
  onDateRangeChange,
}: {
  total: number;
  latencyMs: number | null;
  breakdown: SearchModeBreakdown;
  availableCourts: string[];
  selectedCourts: Set<string>;
  onToggleCourt: (court: string) => void;
  dateRange: DateRange;
  onDateRangeChange: (range: DateRange) => void;
}) {
  const matched = breakdown.keywordOnly + breakdown.semanticOnly + breakdown.hybrid;
  const hasFilters = selectedCourts.size > 0 || dateRange.from !== "" || dateRange.to !== "";

  return (
    <div className="flex flex-col gap-4">
      <section className="glass rounded-xl p-4">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <Gauge className="h-4 w-4 text-primary" aria-hidden />
          This search
        </h2>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <Metric label="Results" value={total.toLocaleString()} />
          <Metric label="Latency" value={latencyMs != null ? `${latencyMs.toFixed(0)} ms` : "—"} />
        </div>

        <Separator className="my-4" />

        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Retrieval path
        </p>

        {/* Proportional bar rather than three numbers: the point is how the
            two retrieval paths contributed relative to each other, which a
            list of counts makes you compute yourself. */}
        {matched > 0 ? (
          <div
            className="mt-2.5 flex h-1.5 w-full overflow-hidden rounded-full bg-secondary"
            role="img"
            aria-label={`${breakdown.hybrid} both paths, ${breakdown.keywordOnly} keyword only, ${breakdown.semanticOnly} semantic only`}
          >
            <Segment value={breakdown.hybrid} total={matched} className="bg-both" />
            <Segment value={breakdown.keywordOnly} total={matched} className="bg-keyword" />
            <Segment value={breakdown.semanticOnly} total={matched} className="bg-semantic" />
          </div>
        ) : null}

        <ul className="mt-3 flex flex-col gap-1.5 text-sm">
          <LegendRow dot="bg-both" label="Both paths" value={breakdown.hybrid} />
          <LegendRow dot="bg-keyword" label="Keyword only" value={breakdown.keywordOnly} />
          <LegendRow dot="bg-semantic" label="Semantic only" value={breakdown.semanticOnly} />
        </ul>
      </section>

      <section className="glass rounded-xl p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-medium">
            <SlidersHorizontal className="h-4 w-4 text-primary" aria-hidden />
            Filters
          </h2>
          {hasFilters ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs"
              onClick={() => {
                for (const court of selectedCourts) onToggleCourt(court);
                onDateRangeChange({ from: "", to: "" });
              }}
            >
              <RotateCcw className="h-3 w-3" aria-hidden />
              Reset
            </Button>
          ) : null}
        </div>

        <div className="mt-4 flex flex-col gap-2">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Court</p>
          {availableCourts.length === 0 ? (
            <p className="text-sm text-muted-foreground">Run a search to see courts here.</p>
          ) : (
            availableCourts.map((court) => (
              <div key={court} className="flex items-center gap-2.5">
                <Checkbox
                  id={`court-${court}`}
                  checked={selectedCourts.has(court)}
                  onCheckedChange={() => onToggleCourt(court)}
                />
                <Label htmlFor={`court-${court}`} className="text-sm font-normal">
                  {court}
                </Label>
              </div>
            ))
          )}
        </div>

        <Separator className="my-4" />

        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Decision date
          </p>
          <div className="flex items-center gap-2">
            <Label htmlFor="date-from" className="sr-only">
              From date
            </Label>
            <input
              id="date-from"
              type="date"
              value={dateRange.from}
              onChange={(e) => onDateRangeChange({ ...dateRange, from: e.target.value })}
              className="w-full rounded-lg border bg-transparent px-2.5 py-1.5 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            />
            <span className="text-xs text-muted-foreground">to</span>
            <Label htmlFor="date-to" className="sr-only">
              To date
            </Label>
            <input
              id="date-to"
              type="date"
              value={dateRange.to}
              onChange={(e) => onDateRangeChange({ ...dateRange, to: e.target.value })}
              className="w-full rounded-lg border bg-transparent px-2.5 py-1.5 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Filters narrow the results already returned; they don&apos;t re-query the API.
          </p>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-secondary/60 px-3 py-2.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tracking-tight tabular-nums">{value}</p>
    </div>
  );
}

function Segment({ value, total, className }: { value: number; total: number; className: string }) {
  if (value <= 0) return null;
  return <span className={className} style={{ width: `${(value / total) * 100}%` }} />;
}

function LegendRow({ dot, label, value }: { dot: string; label: string; value: number }) {
  return (
    <li className="flex items-center justify-between gap-2">
      <span className="flex items-center gap-2 text-muted-foreground">
        <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
        {label}
      </span>
      <span className="font-medium tabular-nums">{value}</span>
    </li>
  );
}

"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Results</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Stat label="Total results" value={total.toLocaleString()} />
          <Stat label="Search latency" value={latencyMs != null ? `${latencyMs.toFixed(0)} ms` : "—"} />
          <Separator />
          <div className="space-y-1">
            <p className="font-medium">Match breakdown</p>
            <Stat label="Keyword only" value={String(breakdown.keywordOnly)} />
            <Stat label="Semantic only" value={String(breakdown.semanticOnly)} />
            <Stat label="Hybrid (both)" value={String(breakdown.hybrid)} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="space-y-2">
            <p className="font-medium">Court</p>
            {availableCourts.length === 0 ? (
              <p className="text-muted-foreground">Search to see courts in the results.</p>
            ) : (
              <div className="space-y-2">
                {availableCourts.map((court) => (
                  <div key={court} className="flex items-center gap-2">
                    <Checkbox
                      id={`court-${court}`}
                      checked={selectedCourts.has(court)}
                      onCheckedChange={() => onToggleCourt(court)}
                    />
                    <Label htmlFor={`court-${court}`} className="font-normal">
                      {court}
                    </Label>
                  </div>
                ))}
              </div>
            )}
          </div>
          <Separator />
          <div className="space-y-2">
            <p className="font-medium">Decision date</p>
            <div className="flex items-center gap-2">
              <Label htmlFor="date-from" className="sr-only">
                From
              </Label>
              <input
                id="date-from"
                type="date"
                value={dateRange.from}
                onChange={(e) => onDateRangeChange({ ...dateRange, from: e.target.value })}
                className="w-full rounded-md border bg-transparent px-2 py-1.5 text-sm"
              />
              <span className="text-muted-foreground">to</span>
              <Label htmlFor="date-to" className="sr-only">
                To
              </Label>
              <input
                id="date-to"
                type="date"
                value={dateRange.to}
                onChange={(e) => onDateRangeChange({ ...dateRange, to: e.target.value })}
                className="w-full rounded-md border bg-transparent px-2 py-1.5 text-sm"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

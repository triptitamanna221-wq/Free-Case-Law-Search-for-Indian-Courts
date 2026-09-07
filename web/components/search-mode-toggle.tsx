"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { isValidSearchMode } from "@/lib/search-params";
import type { SearchMode } from "@/lib/types";

// The dot colours match the result cards' match badges and the breakdown bar,
// so "semantic" means the same colour everywhere in the UI.
const OPTIONS: { value: SearchMode; label: string; dot: string }[] = [
  { value: "hybrid", label: "Keyword + Semantic", dot: "bg-both" },
  { value: "keyword", label: "Keyword only", dot: "bg-keyword" },
  { value: "semantic", label: "Semantic only", dot: "bg-semantic" },
];

export function SearchModeToggle({
  value,
  onChange,
}: {
  value: SearchMode;
  onChange: (mode: SearchMode) => void;
}) {
  return (
    <ToggleGroup
      value={[value]}
      onValueChange={(next) => {
        // single-select (multiple defaults to false): next holds at most one
        // value, but Base UI's ToggleGroup is array-shaped regardless.
        const chosen = next[0];
        if (isValidSearchMode(chosen)) onChange(chosen);
      }}
      variant="outline"
      className="glass flex-wrap justify-center rounded-lg p-1"
      aria-label="Search mode"
    >
      {OPTIONS.map((option) => (
        <ToggleGroupItem
          key={option.value}
          value={option.value}
          aria-label={option.label}
          className="gap-2 rounded-md border-0 text-xs sm:text-sm"
        >
          <span className={`h-1.5 w-1.5 rounded-full ${option.dot}`} aria-hidden />
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

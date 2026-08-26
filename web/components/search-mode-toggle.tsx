"use client";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { isValidSearchMode } from "@/lib/search-params";
import type { SearchMode } from "@/lib/types";

const OPTIONS: { value: SearchMode; label: string }[] = [
  { value: "hybrid", label: "Keyword + Semantic" },
  { value: "keyword", label: "Keyword Only" },
  { value: "semantic", label: "Semantic Only" },
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
      className="flex-wrap justify-center"
      aria-label="Search mode"
    >
      {OPTIONS.map((option) => (
        <ToggleGroupItem key={option.value} value={option.value} aria-label={option.label}>
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

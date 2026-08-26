"use client";

import { Loader2, Search } from "lucide-react";

import { SearchModeToggle } from "@/components/search-mode-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { SearchMode } from "@/lib/types";

export function SearchBox({
  query,
  mode,
  isLoading,
  onQueryChange,
  onModeChange,
  onSubmit,
}: {
  query: string;
  mode: SearchMode;
  isLoading: boolean;
  onQueryChange: (query: string) => void;
  onModeChange: (mode: SearchMode) => void;
  onSubmit: () => void;
}) {
  return (
    <form
      className="mx-auto flex w-full max-w-3xl flex-col items-center gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="flex w-full gap-2">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search judgments — e.g. arbitration clause, oppression and mismanagement..."
            className="pl-9"
            aria-label="Search judgments"
          />
        </div>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Searching...
            </>
          ) : (
            "Search"
          )}
        </Button>
      </div>
      <SearchModeToggle value={mode} onChange={onModeChange} />
    </form>
  );
}

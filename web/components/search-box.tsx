"use client";

import { Loader2, Search } from "lucide-react";
import { useCallback, useId, useMemo, useRef, useState } from "react";

import { SearchModeToggle } from "@/components/search-mode-toggle";
import { EXAMPLE_QUERIES, SearchSuggestions } from "@/components/search-suggestions";
import { Button } from "@/components/ui/button";
import { useRecentSearches } from "@/lib/use-recent-searches";
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
  const listboxId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const { recent, remember, clear } = useRecentSearches();

  const options = useMemo(() => [...recent, ...EXAMPLE_QUERIES], [recent]);
  const optionId = useCallback((index: number) => `${listboxId}-opt-${index}`, [listboxId]);

  const commit = useCallback(
    (value: string) => {
      onQueryChange(value);
      remember(value);
      setOpen(false);
      setActiveIndex(-1);
      inputRef.current?.blur();
    },
    [onQueryChange, remember]
  );

  const handleSubmit = useCallback(() => {
    if (query.trim()) remember(query);
    setOpen(false);
    setActiveIndex(-1);
    onSubmit();
  }, [query, remember, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        setOpen(false);
        setActiveIndex(-1);
        return;
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!open) {
          setOpen(true);
          setActiveIndex(e.key === "ArrowDown" ? 0 : options.length - 1);
          return;
        }
        // wraps at both ends, so the list is traversable in one direction
        const delta = e.key === "ArrowDown" ? 1 : -1;
        setActiveIndex((prev) => (prev + delta + options.length) % options.length);
        return;
      }
      if (e.key === "Enter" && open && activeIndex >= 0) {
        // a highlighted suggestion wins over the raw input text
        e.preventDefault();
        commit(options[activeIndex]);
      }
    },
    [open, options, activeIndex, commit]
  );

  return (
    <section className="relative isolate">
      {/* decorative only -- aria-hidden so it never reaches the a11y tree */}
      <div className="pointer-events-none absolute inset-x-0 -top-8 -z-10 h-72" aria-hidden>
        <div className="hero-halo absolute inset-0" />
        <div className="hero-grid absolute inset-0" />
      </div>

      <div className="mx-auto flex max-w-3xl flex-col items-center gap-5 pt-10 pb-2 text-center sm:pt-14">
        <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          Search Indian case law by{" "}
          <span className="text-primary">meaning</span>, not just keywords
        </h1>
        <p className="max-w-xl text-sm text-balance text-muted-foreground">
          Hybrid retrieval over Supreme Court judgments — BM25 full-text and vector similarity,
          fused with reciprocal rank fusion.
        </p>

        <form
          className="relative w-full"
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
        >
          <div className="flex w-full flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search
                className="pointer-events-none absolute top-1/2 left-4 h-4.5 w-4.5 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  onQueryChange(e.target.value);
                  setActiveIndex(-1);
                }}
                onFocus={() => setOpen(true)}
                // a blur closes the dropdown; suggestion rows use onMouseDown
                // so their selection lands before this fires
                onBlur={() => {
                  setOpen(false);
                  setActiveIndex(-1);
                }}
                onKeyDown={handleKeyDown}
                placeholder="e.g. oppression and mismanagement of a company"
                aria-label="Search judgments"
                role="combobox"
                aria-expanded={open}
                aria-controls={listboxId}
                aria-autocomplete="list"
                aria-activedescendant={
                  open && activeIndex >= 0 ? optionId(activeIndex) : undefined
                }
                className="glass h-12 w-full rounded-xl pr-4 pl-11 text-base shadow-sm transition-shadow placeholder:text-muted-foreground/70 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none sm:text-sm"
              />
            </div>
            <Button type="submit" disabled={isLoading} size="lg" className="h-12 px-6 sm:w-auto">
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  Searching…
                </>
              ) : (
                "Search"
              )}
            </Button>
          </div>

          {open ? (
            <SearchSuggestions
              id={listboxId}
              recent={recent}
              activeIndex={activeIndex}
              optionIds={optionId}
              onSelect={commit}
              onClearRecent={clear}
            />
          ) : null}
        </form>

        <SearchModeToggle value={mode} onChange={onModeChange} />
      </div>
    </section>
  );
}

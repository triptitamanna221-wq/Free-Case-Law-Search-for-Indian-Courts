"use client";

import { Clock, Sparkles, X } from "lucide-react";

/* Labelled "Try these", not "Trending". There's no analytics pipeline behind
   this app, so calling a hardcoded list trending would be presenting invented
   usage data as real. These are curated examples chosen because they actually
   return results against the seeded corpus. */
export const EXAMPLE_QUERIES = [
  "constitutional validity of a statute",
  "a company run into the ground by its own directors",
  "severability of an invalid provision",
  "levy of tax on inter-State sales",
] as const;

export function SearchSuggestions({
  id,
  recent,
  activeIndex,
  optionIds,
  onSelect,
  onClearRecent,
}: {
  id: string;
  recent: string[];
  activeIndex: number;
  optionIds: (index: number) => string;
  onSelect: (query: string) => void;
  onClearRecent: () => void;
}) {
  // Arrow-key navigation treats both groups as one flat list, so recent items
  // occupy [0, recent.length) and examples follow. Derived rather than
  // accumulated in a counter: mutating across map callbacks during render is
  // exactly what react-hooks/immutability forbids, and it desyncs if either
  // group re-renders independently.
  const exampleOffset = recent.length;

  return (
    <div
      className="glass absolute top-full z-50 mt-2 w-full overflow-hidden rounded-xl p-1.5 shadow-lg shadow-black/5"
      role="presentation"
    >
      <ul id={id} role="listbox" aria-label="Search suggestions" className="max-h-80 overflow-y-auto">
        {recent.length > 0 ? (
          <>
            <li
              role="presentation"
              className="flex items-center justify-between px-2.5 pt-1.5 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
            >
              <span className="flex items-center gap-1.5">
                <Clock className="h-3 w-3" aria-hidden />
                Recent
              </span>
              <button
                type="button"
                // onMouseDown, not onClick: the input's blur handler closes
                // this dropdown, and blur fires before click would.
                onMouseDown={(e) => {
                  e.preventDefault();
                  onClearRecent();
                }}
                className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] normal-case hover:bg-secondary hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <X className="h-3 w-3" aria-hidden />
                Clear
              </button>
            </li>
            {recent.map((query, index) => (
              <SuggestionRow
                key={`recent-${query}`}
                id={optionIds(index)}
                label={query}
                active={index === activeIndex}
                icon={<Clock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />}
                onSelect={onSelect}
              />
            ))}
          </>
        ) : null}

        <li
          role="presentation"
          className="flex items-center gap-1.5 px-2.5 pt-2 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground uppercase"
        >
          <Sparkles className="h-3 w-3" aria-hidden />
          Try these
        </li>
        {EXAMPLE_QUERIES.map((query, i) => {
          const index = exampleOffset + i;
          return (
            <SuggestionRow
              key={`example-${query}`}
              id={optionIds(index)}
              label={query}
              active={index === activeIndex}
              icon={<Sparkles className="h-3.5 w-3.5 shrink-0 text-primary/70" aria-hidden />}
              onSelect={onSelect}
            />
          );
        })}
      </ul>
    </div>
  );
}

function SuggestionRow({
  id,
  label,
  active,
  icon,
  onSelect,
}: {
  id: string;
  label: string;
  active: boolean;
  icon: React.ReactNode;
  onSelect: (query: string) => void;
}) {
  return (
    <li
      id={id}
      role="option"
      aria-selected={active}
      onMouseDown={(e) => {
        e.preventDefault();
        onSelect(label);
      }}
      className={`flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${
        active ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/60"
      }`}
    >
      {icon}
      <span className="truncate">{label}</span>
    </li>
  );
}

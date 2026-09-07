"use client";

import { useCallback, useSyncExternalStore } from "react";

const STORAGE_KEY = "cls:recent-searches";
const MAX_RECENT = 6;

/* A module-level store read through useSyncExternalStore, rather than
   useState seeded in an effect. Two reasons: the server has no localStorage,
   so a lazy useState initializer would render [] on the server and a
   populated list on the client (hydration mismatch); and seeding via effect
   trips react-hooks/set-state-in-effect. useSyncExternalStore is built for
   exactly this -- an external, mutable source that differs between server
   and client -- and takes a separate server snapshot. */
let cache: string[] = [];
let cacheLoaded = false;
const listeners = new Set<() => void>();

const EMPTY: string[] = [];

function read(): string[] {
  // Every access is guarded: localStorage throws outright in some contexts
  // (Safari private mode, embedded webviews, site-data blocked), not merely
  // returning null.
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return EMPTY;
    return parsed.filter((v): v is string => typeof v === "string").slice(0, MAX_RECENT);
  } catch {
    return EMPTY;
  }
}

function emit(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): string[] {
  if (!cacheLoaded) {
    cache = read();
    cacheLoaded = true;
  }
  return cache;
}

// The server renders as though nothing has been searched yet.
function getServerSnapshot(): string[] {
  return EMPTY;
}

export function useRecentSearches(): {
  recent: string[];
  remember: (query: string) => void;
  clear: () => void;
} {
  const recent = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const remember = useCallback((query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;
    // Case-insensitive de-dupe, most recent first, so re-running a search
    // promotes it rather than adding a near-duplicate row.
    const next = [trimmed, ...getSnapshot().filter((q) => q.toLowerCase() !== trimmed.toLowerCase())].slice(
      0,
      MAX_RECENT
    );
    cache = next;
    cacheLoaded = true;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Persisting is a convenience; an in-memory list is still correct for
      // this session if storage is unavailable.
    }
    emit();
  }, []);

  const clear = useCallback(() => {
    cache = EMPTY;
    cacheLoaded = true;
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // same as above -- nothing to recover from
    }
    emit();
  }, []);

  return { recent, remember, clear };
}

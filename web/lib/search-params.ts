import type { SearchMode } from "./types";

export const SEARCH_MODES: readonly SearchMode[] = ["hybrid", "keyword", "semantic"] as const;
export const DEFAULT_SEARCH_MODE: SearchMode = "hybrid";

/** Matches the backend's SearchRequest.query Field(min_length=1, max_length=500)
 * (app/schemas/search.py) -- kept in sync by hand since the two live in
 * different languages/repos-within-a-repo. */
export const MAX_QUERY_LENGTH = 500;

export function isValidSearchMode(value: string | null | undefined): value is SearchMode {
  return value != null && (SEARCH_MODES as readonly string[]).includes(value);
}

export interface QueryValidationResult {
  valid: boolean;
  error: string | null;
  /** Trimmed query, only meaningful when valid is true. */
  normalized: string;
}

export function validateQuery(rawQuery: string): QueryValidationResult {
  const normalized = rawQuery.trim();
  if (normalized.length === 0) {
    return { valid: false, error: "Enter a search term.", normalized };
  }
  if (normalized.length > MAX_QUERY_LENGTH) {
    return {
      valid: false,
      error: `Search terms must be ${MAX_QUERY_LENGTH} characters or fewer.`,
      normalized,
    };
  }
  return { valid: true, error: null, normalized };
}

export interface ParsedSearchState {
  query: string;
  mode: SearchMode;
}

/** Reads the shareable-link state (?q=...&mode=...) out of a URLSearchParams.
 * An invalid/missing mode silently falls back to the default rather than
 * erroring -- a stale or hand-edited URL shouldn't break the page. */
export function parseSearchState(params: URLSearchParams): ParsedSearchState {
  const query = params.get("q") ?? "";
  const modeParam = params.get("mode");
  const mode = isValidSearchMode(modeParam) ? modeParam : DEFAULT_SEARCH_MODE;
  return { query, mode };
}

/** Builds the query-string form of a search state, omitting mode when it's
 * the default so shareable links stay short for the common case. */
export function buildSearchParams(state: ParsedSearchState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.query) {
    params.set("q", state.query);
  }
  if (state.mode !== DEFAULT_SEARCH_MODE) {
    params.set("mode", state.mode);
  }
  return params;
}

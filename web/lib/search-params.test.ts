import { describe, expect, it } from "vitest";

import {
  buildSearchParams,
  DEFAULT_SEARCH_MODE,
  isValidSearchMode,
  MAX_QUERY_LENGTH,
  parseSearchState,
  validateQuery,
} from "./search-params";

describe("validateQuery", () => {
  it("rejects an empty query", () => {
    const result = validateQuery("");
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/enter a search term/i);
  });

  it("rejects a whitespace-only query", () => {
    const result = validateQuery("   \n\t  ");
    expect(result.valid).toBe(false);
  });

  it("accepts and trims a normal query", () => {
    const result = validateQuery("  arbitration clause  ");
    expect(result.valid).toBe(true);
    expect(result.error).toBeNull();
    expect(result.normalized).toBe("arbitration clause");
  });

  it("rejects a query longer than the backend's max length", () => {
    const tooLong = "a".repeat(MAX_QUERY_LENGTH + 1);
    const result = validateQuery(tooLong);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(new RegExp(String(MAX_QUERY_LENGTH)));
  });

  it("accepts a query at exactly the max length", () => {
    const exact = "a".repeat(MAX_QUERY_LENGTH);
    expect(validateQuery(exact).valid).toBe(true);
  });
});

describe("isValidSearchMode", () => {
  it("accepts the three real modes", () => {
    expect(isValidSearchMode("hybrid")).toBe(true);
    expect(isValidSearchMode("keyword")).toBe(true);
    expect(isValidSearchMode("semantic")).toBe(true);
  });

  it("rejects unknown values, null, and undefined", () => {
    expect(isValidSearchMode("fuzzy")).toBe(false);
    expect(isValidSearchMode(null)).toBe(false);
    expect(isValidSearchMode(undefined)).toBe(false);
    expect(isValidSearchMode("")).toBe(false);
  });
});

describe("parseSearchState", () => {
  it("reads q and mode from the URL", () => {
    const state = parseSearchState(new URLSearchParams("q=arbitration&mode=keyword"));
    expect(state).toEqual({ query: "arbitration", mode: "keyword" });
  });

  it("defaults mode to hybrid when absent", () => {
    const state = parseSearchState(new URLSearchParams("q=arbitration"));
    expect(state.mode).toBe(DEFAULT_SEARCH_MODE);
  });

  it("falls back to the default mode for an invalid/tampered mode param", () => {
    const state = parseSearchState(new URLSearchParams("q=arbitration&mode=not-a-real-mode"));
    expect(state.mode).toBe(DEFAULT_SEARCH_MODE);
  });

  it("defaults query to an empty string when absent", () => {
    const state = parseSearchState(new URLSearchParams(""));
    expect(state.query).toBe("");
  });
});

describe("buildSearchParams", () => {
  it("includes q and a non-default mode", () => {
    const params = buildSearchParams({ query: "arbitration", mode: "semantic" });
    expect(params.get("q")).toBe("arbitration");
    expect(params.get("mode")).toBe("semantic");
  });

  it("omits mode when it's the default, to keep shareable links short", () => {
    const params = buildSearchParams({ query: "arbitration", mode: "hybrid" });
    expect(params.get("q")).toBe("arbitration");
    expect(params.has("mode")).toBe(false);
  });

  it("omits q when the query is empty", () => {
    const params = buildSearchParams({ query: "", mode: "hybrid" });
    expect(params.has("q")).toBe(false);
  });

  it("round-trips through parseSearchState", () => {
    const original = { query: "oppression and mismanagement", mode: "keyword" as const };
    const roundTripped = parseSearchState(buildSearchParams(original));
    expect(roundTripped).toEqual(original);
  });
});

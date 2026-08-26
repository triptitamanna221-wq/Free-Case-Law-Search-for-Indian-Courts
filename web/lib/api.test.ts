import { describe, expect, it } from "vitest";

import { toSearchOutcome } from "./api";
import type { SearchResponse, SearchResult } from "./types";

function makeResult(overrides: Partial<SearchResult>): SearchResult {
  return {
    judgment_id: 1,
    chunk_id: 1,
    title: "Test Case",
    court: "Supreme Court of India",
    decision_date: "2020-01-01",
    snippet: "snippet",
    fused_score: 0.5,
    matched_keyword: false,
    matched_semantic: false,
    ...overrides,
  };
}

describe("toSearchOutcome", () => {
  it("counts keyword-only, semantic-only, and hybrid results correctly", () => {
    const response: SearchResponse = {
      query: "test",
      took_ms: 12.3,
      results: [
        makeResult({ judgment_id: 1, matched_keyword: true, matched_semantic: false }),
        makeResult({ judgment_id: 2, matched_keyword: false, matched_semantic: true }),
        makeResult({ judgment_id: 3, matched_keyword: true, matched_semantic: true }),
        makeResult({ judgment_id: 4, matched_keyword: true, matched_semantic: true }),
      ],
    };

    const outcome = toSearchOutcome(response);

    expect(outcome.breakdown).toEqual({ keywordOnly: 1, semanticOnly: 1, hybrid: 2 });
    expect(outcome.total).toBe(4);
    expect(outcome.latencyMs).toBe(12.3);
    expect(outcome.query).toBe("test");
  });

  it("handles an empty results list without error", () => {
    const response: SearchResponse = { query: "nothing", took_ms: 5, results: [] };
    const outcome = toSearchOutcome(response);
    expect(outcome.total).toBe(0);
    expect(outcome.breakdown).toEqual({ keywordOnly: 0, semanticOnly: 0, hybrid: 0 });
    expect(outcome.results).toEqual([]);
  });

  it("a result matching neither flag is not counted in any breakdown bucket", () => {
    // shouldn't happen in practice (RRF only returns chunk_ids present in at
    // least one input list), but the mapping must not silently miscount it.
    const response: SearchResponse = {
      query: "test",
      took_ms: 1,
      results: [makeResult({ matched_keyword: false, matched_semantic: false })],
    };
    const outcome = toSearchOutcome(response);
    expect(outcome.breakdown).toEqual({ keywordOnly: 0, semanticOnly: 0, hybrid: 0 });
    expect(outcome.total).toBe(1);
  });
});

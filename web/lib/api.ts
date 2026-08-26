import { buildMockSearchResponse, getMockJudgment } from "./mock-data";
import type { JudgmentDetail, SearchMode, SearchOutcome, SearchResponse } from "./types";

/** Demo mode: exercises the full UI with no backend at all. Never a silent
 * fallback on a real request failure -- see searchJudgments/getJudgment. */
const USE_MOCK_DATA = process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true";
const REQUEST_TIMEOUT_MS = 10_000;
const MOCK_LATENCY_MS = 150;

export type ApiErrorKind = "network" | "timeout" | "server" | "client" | "not_found";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;

  constructor(message: string, kind: ApiErrorKind, status?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

function classifyStatus(status: number): ApiErrorKind {
  if (status === 404) return "not_found";
  if (status >= 500) return "server";
  return "client";
}

function messageForStatus(kind: ApiErrorKind, status: number): string {
  switch (kind) {
    case "not_found":
      return "Judgment not found.";
    case "server":
      return "Search service temporarily unavailable.";
    default:
      return `Request failed (${status}).`;
  }
}

async function fetchWithTimeout(input: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("The search took too long to respond.", "timeout");
    }
    throw new ApiError(
      "Could not reach the search API. Check your connection or try again later.",
      "network"
    );
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Derives total/breakdown client-side, since the real backend doesn't
 * compute either itself: it has no COUNT query (total is just the returned
 * result count -- true server-side pagination isn't implemented, see
 * web/README.md) and no server-side grouping (each result already carries
 * matched_keyword/matched_semantic, which is a more accurate source for the
 * breakdown than a separately-computed server total would be). Exported for
 * unit testing.
 */
export function toSearchOutcome(response: SearchResponse): SearchOutcome {
  let keywordOnly = 0;
  let semanticOnly = 0;
  let hybrid = 0;
  for (const r of response.results) {
    if (r.matched_keyword && r.matched_semantic) hybrid += 1;
    else if (r.matched_keyword) keywordOnly += 1;
    else if (r.matched_semantic) semanticOnly += 1;
  }
  return {
    query: response.query,
    results: response.results,
    latencyMs: response.took_ms,
    total: response.results.length,
    breakdown: { keywordOnly, semanticOnly, hybrid },
  };
}

export interface SearchParams {
  query: string;
  mode: SearchMode;
  limit: number;
  court?: string | null;
}

export async function searchJudgments(params: SearchParams): Promise<SearchOutcome> {
  if (USE_MOCK_DATA) {
    await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));
    return toSearchOutcome(buildMockSearchResponse(params.query, params.limit));
  }

  const response = await fetchWithTimeout("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: params.query,
      search_mode: params.mode,
      limit: params.limit,
      court: params.court ?? null,
    }),
  });

  if (!response.ok) {
    const kind = classifyStatus(response.status);
    throw new ApiError(messageForStatus(kind, response.status), kind, response.status);
  }

  const data: SearchResponse = await response.json();
  return toSearchOutcome(data);
}

export async function getJudgment(id: number): Promise<JudgmentDetail> {
  if (USE_MOCK_DATA) {
    await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS * 0.6));
    const judgment = getMockJudgment(id);
    if (!judgment) throw new ApiError("Judgment not found.", "not_found", 404);
    return judgment;
  }

  const response = await fetchWithTimeout(`/api/judgments/${id}`);
  if (!response.ok) {
    const kind = classifyStatus(response.status);
    throw new ApiError(messageForStatus(kind, response.status), kind, response.status);
  }
  return response.json();
}

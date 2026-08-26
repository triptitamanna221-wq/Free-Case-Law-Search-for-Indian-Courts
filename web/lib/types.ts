export type SearchMode = "hybrid" | "keyword" | "semantic";

export interface SearchResult {
  judgment_id: number;
  chunk_id: number;
  title: string;
  court: string | null;
  decision_date: string | null;
  snippet: string;
  fused_score: number;
  matched_keyword: boolean;
  matched_semantic: boolean;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  took_ms: number;
}

export interface SearchModeBreakdown {
  keywordOnly: number;
  semanticOnly: number;
  hybrid: number;
}

/** Everything the results/metadata panels need, derived client-side from the
 * real API response -- the backend doesn't compute total/breakdown itself
 * (see lib/api.ts's toSearchOutcome for why). */
export interface SearchOutcome {
  query: string;
  results: SearchResult[];
  latencyMs: number;
  total: number;
  breakdown: SearchModeBreakdown;
}

export interface JudgmentDetail {
  id: number;
  title: string;
  court: string | null;
  case_type: string | null;
  decision_date: string | null;
  judges: string[] | null;
  petitioner: string | null;
  respondent: string | null;
  raw_text: string;
  source_dataset: string;
  source_url: string | null;
  created_at: string;
}

export interface SearchFilters {
  court: string | null;
  dateFrom: string | null;
  dateTo: string | null;
}

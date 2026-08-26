import type { JudgmentDetail, SearchResponse } from "./types";

/**
 * Demo-mode data only. Used exclusively when NEXT_PUBLIC_USE_MOCK_DATA=true
 * (see lib/api.ts) -- never as a silent fallback for a real, failed API call.
 * A real backend outage must show the real error UI, not fake results.
 */

const MOCK_RESULTS: SearchResponse["results"] = [
  {
    judgment_id: 1001,
    chunk_id: 5001,
    title: "Kesavananda Bharati vs State of Kerala",
    court: "Supreme Court of India",
    decision_date: "1973-04-24",
    snippet:
      "...the doctrine of basic structure holds that certain fundamental features of the Constitution cannot be abrogated by amendment, even under the wide amending power conferred by Article 368...",
    fused_score: 0.91,
    matched_keyword: true,
    matched_semantic: true,
  },
  {
    judgment_id: 1002,
    chunk_id: 5002,
    title: "Maneka Gandhi vs Union of India",
    court: "Supreme Court of India",
    decision_date: "1978-01-25",
    snippet:
      "...the right to life and personal liberty under Article 21 cannot be construed narrowly; any procedure established by law must itself be fair, just, and reasonable...",
    fused_score: 0.84,
    matched_keyword: false,
    matched_semantic: true,
  },
  {
    judgment_id: 1003,
    chunk_id: 5003,
    title: "Vishaka vs State of Rajasthan",
    court: "Supreme Court of India",
    decision_date: "1997-08-13",
    snippet:
      "...in the absence of enacted law providing for the effective enforcement of the basic human right of gender equality, guidelines are laid down to be treated as law under Article 141...",
    fused_score: 0.79,
    matched_keyword: true,
    matched_semantic: false,
  },
  {
    judgment_id: 1004,
    chunk_id: 5004,
    title: "Union of India vs Raghubir Singh",
    court: "Delhi High Court",
    decision_date: "1989-11-02",
    snippet:
      "...the arbitration clause contained in the agreement did not survive the termination of the underlying contract for the purposes disputed by the appellant...",
    fused_score: 0.63,
    matched_keyword: true,
    matched_semantic: true,
  },
];

export function buildMockSearchResponse(query: string, limit: number): SearchResponse {
  return {
    query,
    results: MOCK_RESULTS.slice(0, limit),
    took_ms: 8.4,
  };
}

const MOCK_JUDGMENTS: Record<number, JudgmentDetail> = {
  1001: {
    id: 1001,
    title: "Kesavananda Bharati vs State of Kerala",
    court: "Supreme Court of India",
    case_type: "Writ Petition",
    decision_date: "1973-04-24",
    judges: ["S.M. Sikri", "A.N. Ray", "D.G. Palekar", "K.K. Mathew", "H.R. Khanna"],
    petitioner: "Kesavananda Bharati",
    respondent: "State of Kerala",
    raw_text:
      "SUPREME COURT OF INDIA\n\nPETITIONER: KESAVANANDA BHARATI\nVs.\nRESPONDENT: STATE OF KERALA\n\n[Demo-mode placeholder text -- this app is running against mock data because NEXT_PUBLIC_USE_MOCK_DATA=true or the real API was unreachable. The doctrine of basic structure holds that certain fundamental features of the Constitution cannot be abrogated by amendment, even under the wide amending power conferred by Article 368. This placeholder repeats to demonstrate the scrollable full-text panel. ".repeat(
        20
      ),
    source_dataset: "mock",
    source_url: null,
    created_at: "2026-01-01T00:00:00Z",
  },
};

export function getMockJudgment(id: number): JudgmentDetail | null {
  return MOCK_JUDGMENTS[id] ?? mockJudgmentFromSearchResult(id);
}

function mockJudgmentFromSearchResult(id: number): JudgmentDetail | null {
  const result = MOCK_RESULTS.find((r) => r.judgment_id === id);
  if (!result) return null;
  return {
    id: result.judgment_id,
    title: result.title,
    court: result.court,
    case_type: "Appeal",
    decision_date: result.decision_date,
    judges: ["Demo Judge A", "Demo Judge B"],
    petitioner: "Demo Petitioner",
    respondent: "Demo Respondent",
    raw_text: `[Demo-mode placeholder] ${result.snippet} `.repeat(15),
    source_dataset: "mock",
    source_url: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

import { describe, expect, it } from "vitest";

import { formatDate, formatJudges, highlightTerms, matchLabel, truncateWords } from "./format";

describe("truncateWords", () => {
  it("leaves short text untouched", () => {
    expect(truncateWords("a short snippet", 100)).toBe("a short snippet");
  });

  it("truncates long text to the word limit and adds an ellipsis", () => {
    const text = Array.from({ length: 150 }, (_, i) => `word${i}`).join(" ");
    const truncated = truncateWords(text, 100);
    expect(truncated.split(/\s+/).length).toBe(100); // the ellipsis is appended to the last word, not a separate token
    expect(truncated.endsWith("…")).toBe(true);
    expect(truncated.startsWith("word0 word1")).toBe(true);
  });
});

describe("highlightTerms", () => {
  it("marks case-insensitive occurrences of query terms", () => {
    const parts = highlightTerms("The Arbitration clause was disputed", "arbitration");
    const highlighted = parts.filter((p) => p.highlight).map((p) => p.text);
    expect(highlighted).toEqual(["Arbitration"]);
  });

  it("ignores short (<3 char) terms to avoid noisy highlighting", () => {
    const parts = highlightTerms("the law of the land", "of");
    expect(parts.every((p) => !p.highlight)).toBe(true);
  });

  it("returns the whole text unhighlighted when there are no real terms", () => {
    const parts = highlightTerms("some text", "");
    expect(parts).toEqual([{ text: "some text", highlight: false }]);
  });

  it("does not crash on regex special characters in the query", () => {
    expect(() => highlightTerms("a (b) c", "(b)")).not.toThrow();
  });
});

describe("matchLabel", () => {
  it("labels hybrid, keyword-only, and semantic-only matches", () => {
    expect(matchLabel(true, true)).toBe("keyword + semantic");
    expect(matchLabel(true, false)).toBe("keyword");
    expect(matchLabel(false, true)).toBe("semantic");
    expect(matchLabel(false, false)).toBe("match");
  });
});

describe("formatDate", () => {
  it("formats a valid ISO date", () => {
    expect(formatDate("2020-01-15")).toMatch(/2020/);
  });

  it("falls back for null or invalid dates", () => {
    expect(formatDate(null)).toBe("Date unknown");
    expect(formatDate("not-a-date")).toBe("Date unknown");
  });
});

describe("formatJudges", () => {
  it("joins a judge list with commas", () => {
    expect(formatJudges(["Judge A", "Judge B"])).toBe("Judge A, Judge B");
  });

  it("falls back for null or empty judges", () => {
    expect(formatJudges(null)).toBe("Bench not recorded");
    expect(formatJudges([])).toBe("Bench not recorded");
  });
});

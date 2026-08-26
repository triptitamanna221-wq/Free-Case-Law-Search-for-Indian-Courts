export function formatDate(iso: string | null): string {
  if (!iso) return "Date unknown";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Date unknown";
  return date.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
}

export function formatJudges(judges: string[] | null): string {
  if (!judges || judges.length === 0) return "Bench not recorded";
  return judges.join(", ");
}

export function matchLabel(matchedKeyword: boolean, matchedSemantic: boolean): string {
  if (matchedKeyword && matchedSemantic) return "keyword + semantic";
  if (matchedKeyword) return "keyword";
  if (matchedSemantic) return "semantic";
  return "match";
}

/** Trims a snippet to ~N words without cutting mid-word. */
export function truncateWords(text: string, maxWords: number): string {
  const words = text.trim().split(/\s+/);
  if (words.length <= maxWords) return text.trim();
  return words.slice(0, maxWords).join(" ") + "…";
}

/** Wraps case-insensitive occurrences of any query term (3+ chars, to avoid
 * highlighting noise like "the"/"of") in <mark> tags. Returns React-safe
 * pieces for dangerouslySetInnerHTML-free rendering. */
export function highlightTerms(text: string, query: string): { text: string; highlight: boolean }[] {
  const terms = Array.from(
    new Set(
      query
        .split(/\s+/)
        .map((t) => t.trim())
        .filter((t) => t.length >= 3)
    )
  );
  if (terms.length === 0) return [{ text, highlight: false }];

  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts
    .filter((part) => part.length > 0)
    .map((part) => ({
      text: part,
      highlight: terms.some((term) => term.toLowerCase() === part.toLowerCase()),
    }));
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

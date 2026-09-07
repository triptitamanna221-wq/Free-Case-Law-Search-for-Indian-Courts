export interface JudgmentSection {
  heading: string;
  body: string;
}

/* Headings that genuinely appear in this corpus (JUDIS-sourced Supreme Court
   text), each on its own line and followed by a colon. Deliberately NOT a
   Facts/Issue/Holding taxonomy: the API returns one raw_text blob with no
   such structure, and inferring those labels would mean captioning text with
   a classification nothing in the data supports. These are transcribed from
   the source, so a section only appears when the document really has it. */
const KNOWN_HEADINGS = [
  "PETITIONER",
  "RESPONDENT",
  "DATE OF JUDGMENT",
  "BENCH",
  "CITATION",
  "ACT",
  "HEADNOTE",
  "JUDGMENT",
] as const;

const HEADING_PATTERN = new RegExp(`^\\s*(${KNOWN_HEADINGS.join("|")})\\s*:\\s*$`, "i");

/**
 * Splits raw judgment text on its own section headings.
 *
 * Returns `[]` when no headings are found, which is the signal to fall back to
 * rendering the document whole — many judgments in the corpus are unstructured
 * and would otherwise be silently reduced to an empty accordion.
 */
export function parseJudgmentSections(rawText: string): JudgmentSection[] {
  if (!rawText.trim()) return [];

  const lines = rawText.split(/\r?\n/);
  const sections: JudgmentSection[] = [];
  let current: JudgmentSection | null = null;
  const preamble: string[] = [];

  for (const line of lines) {
    const match = HEADING_PATTERN.exec(line);
    if (match) {
      if (current) sections.push(current);
      // Normalize casing so "Bench" and "BENCH" don't render as two sections.
      current = { heading: match[1].toUpperCase(), body: "" };
      continue;
    }
    if (current) current.body += line + "\n";
    else preamble.push(line);
  }
  if (current) sections.push(current);

  if (sections.length === 0) return [];

  // Text before the first heading is usually the source URL and court name.
  // Kept rather than dropped, but only when it carries something.
  const lead = preamble.join("\n").trim();
  if (lead) sections.unshift({ heading: "DOCUMENT", body: lead });

  const trimmed = sections
    .map((s) => ({ heading: s.heading, body: s.body.trim() }))
    .filter((s) => s.body.length > 0);

  return mergeConsecutiveDuplicates(trimmed);
}

/* These documents genuinely repeat a heading back to back -- judgment 54, for
   instance, has two adjacent BENCH: blocks (one naming the author, then the
   full coram). Rendering them as two identically-labelled sections looks like
   a bug to a reader, so adjacent repeats are joined. Only *consecutive* ones:
   merging every same-named section would splice together blocks from opposite
   ends of a long judgment that happen to share a label. */
function mergeConsecutiveDuplicates(sections: JudgmentSection[]): JudgmentSection[] {
  return sections.reduce<JudgmentSection[]>((acc, section) => {
    const previous = acc[acc.length - 1];
    if (previous && previous.heading === section.heading) {
      acc[acc.length - 1] = {
        heading: previous.heading,
        body: `${previous.body}\n${section.body}`,
      };
      return acc;
    }
    acc.push(section);
    return acc;
  }, []);
}

/** Title-cases a heading for display: "DATE OF JUDGMENT" -> "Date of judgment". */
export function formatHeading(heading: string): string {
  const lower = heading.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

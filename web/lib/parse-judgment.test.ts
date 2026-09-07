import { describe, expect, it } from "vitest";

import { formatHeading, parseJudgmentSections } from "./parse-judgment";

// Shaped after the real seeded text (judgment 54, BULLION AND GRAIN EXCHANGE).
const REAL_SHAPE = `http://JUDIS.NIC.IN
SUPREME COURT OF INDIA
PETITIONER:
THE BULLION AND GRAIN EXCHANGE LTD.  AND OTHERS

	Vs.

RESPONDENT:
THE STATE OF PUNJAB

DATE OF JUDGMENT:
13/09/1960

BENCH:
GUPTA, K.C. DAS

CITATION:
 1961 AIR  268		  1961 SCR  (1) 668

ACT:
Forward Contracts Tax-Validity of enactment.
`;

describe("parseJudgmentSections", () => {
  it("splits real judgment text on its own headings", () => {
    const sections = parseJudgmentSections(REAL_SHAPE);
    const headings = sections.map((s) => s.heading);

    expect(headings).toContain("PETITIONER");
    expect(headings).toContain("RESPONDENT");
    expect(headings).toContain("CITATION");
    expect(headings).toContain("ACT");
  });

  it("keeps the text preceding the first heading as a DOCUMENT section", () => {
    const [first] = parseJudgmentSections(REAL_SHAPE);
    expect(first.heading).toBe("DOCUMENT");
    expect(first.body).toContain("SUPREME COURT OF INDIA");
  });

  it("attaches body text to the heading above it", () => {
    const sections = parseJudgmentSections(REAL_SHAPE);
    const respondent = sections.find((s) => s.heading === "RESPONDENT");
    expect(respondent?.body).toBe("THE STATE OF PUNJAB");
  });

  it("returns [] for unstructured text so callers can render it whole", () => {
    // The signal that matters: many judgments in the corpus carry no headings
    // at all, and must not collapse into an empty accordion.
    expect(parseJudgmentSections("A judgment with no headings at all.")).toEqual([]);
    expect(parseJudgmentSections("")).toEqual([]);
    expect(parseJudgmentSections("   \n  \n ")).toEqual([]);
  });

  it("ignores heading words that appear mid-sentence", () => {
    const text = "The BENCH: considered the matter and the ACT: was upheld in full.";
    // Both words appear, but neither is alone on its line, so neither is a heading.
    expect(parseJudgmentSections(text)).toEqual([]);
  });

  it("normalizes heading case so one section isn't split in two", () => {
    const sections = parseJudgmentSections("Bench:\nA judge\n\nBENCH:\nAnother judge");
    expect(sections.every((s) => s.heading === s.heading.toUpperCase())).toBe(true);
  });

  it("drops headings that have no body", () => {
    const sections = parseJudgmentSections("PETITIONER:\n\nRESPONDENT:\nThe State");
    expect(sections.map((s) => s.heading)).toEqual(["RESPONDENT"]);
  });

  it("merges consecutive repeats of the same heading", () => {
    // Real shape: judgment 54 carries two adjacent BENCH: blocks, which
    // otherwise render as two identical-looking sections.
    const sections = parseJudgmentSections(
      "BENCH:\nGUPTA, K.C. DAS\n\nBENCH:\nDAS, S.K.\nHIDAYATULLAH, M."
    );
    expect(sections).toHaveLength(1);
    expect(sections[0].heading).toBe("BENCH");
    expect(sections[0].body).toContain("GUPTA, K.C. DAS");
    expect(sections[0].body).toContain("HIDAYATULLAH, M.");
  });

  it("does not merge same-named sections separated by another section", () => {
    // Guards against over-merging: two ACT blocks at opposite ends of a
    // judgment are separate discussions, not one continued passage.
    const sections = parseJudgmentSections("ACT:\nFirst act\n\nBENCH:\nA judge\n\nACT:\nSecond act");
    expect(sections.map((s) => s.heading)).toEqual(["ACT", "BENCH", "ACT"]);
  });
});

describe("formatHeading", () => {
  it("title-cases a screaming-caps heading", () => {
    expect(formatHeading("DATE OF JUDGMENT")).toBe("Date of judgment");
    expect(formatHeading("ACT")).toBe("Act");
  });
});

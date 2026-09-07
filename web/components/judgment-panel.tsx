"use client";

import { ChevronDown, Download, Gavel, Loader2, Quote } from "lucide-react";
import { useMemo, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { formatDate, formatJudges } from "@/lib/format";
import { formatHeading, parseJudgmentSections } from "@/lib/parse-judgment";
import type { JudgmentDetail } from "@/lib/types";

function downloadAsText(judgment: JudgmentDetail): void {
  const blob = new Blob([judgment.raw_text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `judgment-${judgment.id}.txt`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function JudgmentPanel({
  open,
  onOpenChange,
  judgment,
  isLoading,
  errorMessage,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  judgment: JudgmentDetail | null;
  isLoading: boolean;
  errorMessage: string | null;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 p-0 sm:max-w-2xl">
        {isLoading ? (
          <PanelSkeleton />
        ) : errorMessage ? (
          <div className="p-6">
            <Alert variant="destructive">
              <AlertTitle>Could not load judgment</AlertTitle>
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          </div>
        ) : judgment ? (
          <JudgmentBody judgment={judgment} />
        ) : (
          <div className="flex h-full items-center justify-center p-6 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function JudgmentBody({ judgment }: { judgment: JudgmentDetail }) {
  const sections = useMemo(() => parseJudgmentSections(judgment.raw_text), [judgment.raw_text]);

  return (
    <>
      <SheetHeader className="gap-3 border-b px-5 py-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Gavel className="h-4 w-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <SheetTitle className="pr-8 font-serif text-lg leading-snug text-balance">
              {judgment.title}
            </SheetTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {judgment.court ?? "Court unknown"}
              {judgment.case_type ? ` · ${judgment.case_type}` : ""} ·{" "}
              {formatDate(judgment.decision_date)}
            </p>
          </div>
        </div>

        {judgment.petitioner || judgment.respondent ? (
          <p className="text-sm">
            <span className="font-medium">{judgment.petitioner ?? "Petitioner unknown"}</span>
            <span className="text-muted-foreground"> vs </span>
            <span className="font-medium">{judgment.respondent ?? "Respondent unknown"}</span>
          </p>
        ) : null}

        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Bench:</span>{" "}
          {formatJudges(judgment.judges)}
        </p>

        <div className="flex flex-wrap items-center gap-2 pt-0.5">
          <Button size="sm" variant="outline" onClick={() => downloadAsText(judgment)}>
            <Download className="h-4 w-4" aria-hidden />
            Download .txt
          </Button>
          {judgment.source_url ? (
            <Button
              size="sm"
              variant="ghost"
              render={
                <a href={judgment.source_url} target="_blank" rel="noreferrer">
                  <Quote className="h-4 w-4" aria-hidden />
                  Source
                </a>
              }
            />
          ) : null}
        </div>
      </SheetHeader>

      <ScrollArea className="h-[calc(100vh-15rem)]">
        <div className="flex flex-col gap-2 px-5 py-4">
          {sections.length > 0 ? (
            sections.map((section, i) => (
              <CollapsibleSection
                key={`${section.heading}-${i}`}
                heading={formatHeading(section.heading)}
                body={section.body}
                // The first two sections carry the identifying detail, so they
                // open by default; the rest stay closed to keep the document
                // scannable rather than a wall of text.
                defaultOpen={i < 2}
              />
            ))
          ) : (
            // Unstructured judgment: no headings to split on, so render whole
            // rather than show an empty accordion.
            <article className="prose-legal whitespace-pre-wrap break-words">
              {judgment.raw_text}
            </article>
          )}
        </div>
      </ScrollArea>
    </>
  );
}

function CollapsibleSection({
  heading,
  body,
  defaultOpen,
}: {
  heading: string;
  body: string;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className="rounded-lg border">
      <h3>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex w-full items-center justify-between gap-3 rounded-lg px-3.5 py-2.5 text-left text-sm font-medium transition-colors hover:bg-secondary/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {heading}
          <ChevronDown
            className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
              open ? "rotate-180" : ""
            }`}
            aria-hidden
          />
        </button>
      </h3>
      {/* grid-template-rows 0fr -> 1fr animates to the content's natural
          height in pure CSS, which height:auto can't do. `hidden` keeps the
          collapsed body out of the accessibility tree and tab order. */}
      <div
        className="grid transition-[grid-template-rows] duration-200 ease-out"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="px-3.5 pb-3.5" hidden={!open}>
            <p className="prose-legal whitespace-pre-wrap break-words text-card-foreground">
              {body}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function PanelSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-6" aria-busy="true">
      <p className="sr-only">Loading judgment…</p>
      <div className="shimmer h-6 w-3/4 rounded bg-secondary" />
      <div className="shimmer h-4 w-1/2 rounded bg-secondary" />
      <div className="shimmer h-4 w-2/5 rounded bg-secondary" />
      <div className="mt-2 flex flex-col gap-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="shimmer h-3 w-full rounded bg-secondary" />
        ))}
      </div>
    </div>
  );
}

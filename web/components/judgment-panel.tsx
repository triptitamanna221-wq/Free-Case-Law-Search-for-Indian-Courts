"use client";

import { Download, Loader2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatJudges } from "@/lib/format";
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
      <SheetContent side="right" className="w-full gap-0 sm:max-w-2xl">
        {isLoading ? (
          <div className="space-y-4 p-6">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="mt-4 h-64 w-full" />
          </div>
        ) : errorMessage ? (
          <div className="p-6">
            <Alert variant="destructive">
              <AlertTitle>Could not load judgment</AlertTitle>
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          </div>
        ) : judgment ? (
          <>
            <SheetHeader>
              <SheetTitle className="pr-8">{judgment.title}</SheetTitle>
              <SheetDescription render={<div className="flex flex-col gap-1 text-sm" />}>
                <span>
                  {judgment.court ?? "Court unknown"}
                  {judgment.case_type ? ` · ${judgment.case_type}` : ""}
                </span>
                <span>{formatDate(judgment.decision_date)}</span>
                <span>Bench: {formatJudges(judgment.judges)}</span>
                {judgment.petitioner || judgment.respondent ? (
                  <span>
                    {judgment.petitioner ?? "Petitioner unknown"} vs{" "}
                    {judgment.respondent ?? "Respondent unknown"}
                  </span>
                ) : null}
              </SheetDescription>
            </SheetHeader>
            <div className="flex items-center gap-2 border-b px-4 pb-4">
              <Button size="sm" variant="outline" onClick={() => downloadAsText(judgment)}>
                <Download className="h-4 w-4" aria-hidden />
                Download .txt
              </Button>
            </div>
            <ScrollArea className="h-[calc(100vh-16rem)] px-4 py-4">
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">
                {judgment.raw_text}
              </pre>
            </ScrollArea>
          </>
        ) : (
          <div className="flex h-full items-center justify-center p-6 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

import { Code2, Scale } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

const REPO_URL = "https://github.com/triptitamanna221-wq/Free-Case-Law-Search-for-Indian-Courts";

export function Header() {
  return (
    <header className="glass sticky top-0 z-40 border-x-0 border-t-0">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link
          href="/"
          className="group flex items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm transition-transform group-hover:scale-105">
            <Scale className="h-4 w-4" aria-hidden />
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-sm font-semibold tracking-tight">Case Law Search</span>
            <span className="hidden text-[11px] text-muted-foreground sm:block">
              Hybrid keyword + semantic retrieval
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            render={
              <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label="View source on GitHub" />
            }
          >
            <Code2 className="h-4 w-4" />
          </Button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

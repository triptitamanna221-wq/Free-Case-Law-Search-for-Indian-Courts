import { Code2, Scale } from "lucide-react";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

const REPO_URL = "https://github.com/triptitamanna221-wq/Free-Case-Law-Search-for-Indian-Courts";

export function Header() {
  return (
    <header className="border-b">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Scale className="h-5 w-5" aria-hidden />
          <span>Case Law Search</span>
        </Link>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            render={<a href={REPO_URL} target="_blank" rel="noreferrer" aria-label="View source on GitHub" />}
          >
            <Code2 className="h-4 w-4" />
          </Button>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

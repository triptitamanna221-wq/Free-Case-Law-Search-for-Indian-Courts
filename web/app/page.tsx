import { Suspense } from "react";

import { SearchPage } from "@/components/search-page";

export default function Page() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-muted-foreground">Loading...</div>}>
      <SearchPage />
    </Suspense>
  );
}

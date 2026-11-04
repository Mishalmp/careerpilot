import { Suspense } from "react";

import { ProblemsPage } from "@/features/practice/ProblemsPage";

// This page loads its data in the browser, so it may block on navigation.
export const instant = false;

export default function Page() {
  // The list reads ?topic=... from the URL, which Next only knows at request time.
  return (
    <Suspense fallback={null}>
      <ProblemsPage />
    </Suspense>
  );
}

import { Suspense } from "react";

import { ProblemPage } from "@/features/practice/ProblemPage";

// This page loads its data in the browser, so it may block on navigation.
export const instant = false;

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ProblemPage />
    </Suspense>
  );
}

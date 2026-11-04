import { Suspense } from "react";

import { JobDetailPage } from "@/features/tracker/JobDetailPage";

// These pages load their data in the browser, so they may block on navigation.
export const instant = false;

export default function Page() {
  return (
    <Suspense fallback={null}>
      <JobDetailPage />
    </Suspense>
  );
}

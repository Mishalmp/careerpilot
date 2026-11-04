import { Suspense } from "react";

import { GuideReaderPage } from "@/features/prep/GuidesPages";

// These pages load their data in the browser, so they may block on navigation.
export const instant = false;

export default function Page() {
  return (
    <Suspense fallback={null}>
      <GuideReaderPage />
    </Suspense>
  );
}

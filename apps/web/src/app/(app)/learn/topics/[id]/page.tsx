import { Suspense } from "react";

import { TopicPage } from "@/features/learn/TopicPage";

// These pages load their data in the browser, so they may block on navigation.
export const instant = false;

export default function Page() {
  return (
    <Suspense fallback={null}>
      <TopicPage />
    </Suspense>
  );
}

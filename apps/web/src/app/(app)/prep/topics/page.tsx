import { TopicsPage } from "@/features/prep/TopicsPage";

// This page loads its data in the browser, so it may block on navigation.
export const instant = false;

export default function Page() {
  return <TopicsPage />;
}

import { ReviewSession } from "@/features/learn/ReviewSession";

// This page loads its data in the browser, so it may block on navigation.
export const instant = false;

export default function Page() {
  return <ReviewSession />;
}

import { GuidesListPage } from "@/features/prep/GuidesPages";

// This page loads its data in the browser, so it may block on navigation.
export const instant = false;

export default function Page() {
  return <GuidesListPage />;
}

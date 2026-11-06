import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ShellPreview } from "./preview";

export const metadata = { title: "Shell preview" };

/** Development-only: the signed-in app shell with a fake session, so it can be checked without a user. */
export default function Page() {
  if (process.env.NODE_ENV === "production") notFound();
  // Suspense: the preview seeds a query cache, which reads the clock, so it must not be prerendered.
  return (
    <Suspense fallback={null}>
      <ShellPreview />
    </Suspense>
  );
}

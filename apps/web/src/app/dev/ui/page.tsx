import { notFound } from "next/navigation";

import { Gallery } from "./gallery";

export const metadata = { title: "UI gallery" };

/** Development-only gallery of every design-system component and state. Hidden in production builds. */
export default function Page() {
  if (process.env.NODE_ENV === "production") notFound();
  return <Gallery />;
}

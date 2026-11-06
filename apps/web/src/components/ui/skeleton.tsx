import * as React from "react";

import { cn } from "@/lib/utils";

/** Placeholder shaped like the content it stands in for. Hidden from screen readers. */
export function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-md bg-surface-hover", className)}
      {...props}
    />
  );
}

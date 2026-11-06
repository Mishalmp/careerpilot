"use client";

import { Switch as SwitchPrimitive } from "radix-ui";
import * as React from "react";

import { cn } from "@/lib/utils";

/** On/off setting that takes effect immediately. Give it a visible label or aria-label. */
export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-transparent bg-input p-0.5",
        "transition-colors duration-[var(--dur-fast)] data-[state=checked]:bg-primary disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block size-4 rounded-full bg-white shadow transition-transform duration-[var(--dur-fast)] data-[state=checked]:translate-x-4" />
    </SwitchPrimitive.Root>
  );
}

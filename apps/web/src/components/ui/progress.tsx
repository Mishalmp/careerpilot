import { Check } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/** A bar for "n of m". `value` is 0 to 100; leave it out for work whose size is not known. */
export function ProgressBar({ value, label, className }: { value?: number | null; label: string; className?: string }) {
  const known = typeof value === "number";
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={known ? Math.round(value) : undefined}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-hover", className)}
    >
      <div
        className={cn("h-full rounded-full bg-primary transition-[width] duration-[var(--dur)]", !known && "w-1/3 animate-pulse")}
        style={known ? { width: `${Math.max(2, Math.min(100, value))}%` } : undefined}
      />
    </div>
  );
}

/** Steps of a longer task: done steps are ticked, the current one is highlighted. */
export function Stepper({
  steps,
  current,
  onSelect,
}: {
  steps: string[];
  current: number;
  /** Only steps before the current one can be opened again. */
  onSelect?: (index: number) => void;
}) {
  return (
    <ol className="flex flex-wrap gap-x-2 gap-y-2" aria-label="Setup steps">
      {steps.map((name, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={name} className="flex items-center gap-2" aria-current={active ? "step" : undefined}>
            <button
              type="button"
              disabled={i > current || !onSelect}
              onClick={() => onSelect?.(i)}
              className={cn(
                "flex items-center gap-2 rounded-full border px-3 py-1 text-[0.8125rem] font-medium transition-colors",
                active && "border-primary bg-accent-soft text-accent-text",
                done && "border-success-text/30 bg-success-soft text-success-text hover:opacity-80",
                !active && !done && "border-border-subtle text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex size-5 items-center justify-center rounded-full text-[0.6875rem]",
                  active ? "bg-primary text-primary-foreground" : done ? "bg-success-text text-surface" : "bg-surface-hover",
                )}
              >
                {done ? <Check className="size-3" aria-hidden="true" /> : i + 1}
              </span>
              {name}
            </button>
            {i < steps.length - 1 ? <span aria-hidden="true" className="hidden h-px w-4 bg-border sm:block" /> : null}
          </li>
        );
      })}
    </ol>
  );
}

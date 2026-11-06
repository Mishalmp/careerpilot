import * as React from "react";

import { cn } from "@/lib/utils";

const control =
  "w-full rounded-md border border-input bg-surface px-3 text-[length:var(--text-base)] text-foreground " +
  "placeholder:text-muted-foreground transition-colors duration-[var(--dur-fast)] " +
  "hover:border-foreground/40 focus-visible:border-ring focus-visible:outline-2 focus-visible:outline-offset-0 " +
  "focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-danger";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(control, "h-[var(--control-h)]", className)} {...props} />;
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(control, "min-h-24 py-2", className)} {...props} />;
}

/** Native select styled like the other controls (best mobile behaviour, fully accessible). */
export function Select({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <select className={cn(control, "h-[var(--control-h)] pr-8", className)} {...props}>
      {children}
    </select>
  );
}

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return <label className={cn("text-[0.8125rem] font-medium text-foreground", className)} {...props} />;
}

/**
 * Label + control + help + error, wired together for screen readers.
 * The control must accept `id` and `aria-describedby`; pass them from the render function.
 */
export function Field({
  label,
  help,
  error,
  children,
  className,
}: {
  label: string;
  help?: string;
  error?: string | null;
  className?: string;
  children: (props: { id: string; "aria-describedby"?: string; "aria-invalid"?: boolean }) => React.ReactNode;
}) {
  const id = React.useId();
  const helpId = help ? `${id}-help` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, helpId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children({ id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })}
      {help ? (
        <p id={helpId} className="text-xs text-muted-foreground">
          {help}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-danger-text">
          {error}
        </p>
      ) : null}
    </div>
  );
}

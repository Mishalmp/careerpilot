import { cn } from "@/lib/utils";

/** The CareerPilot mark: a blue rounded square with a white paper plane. Also at src/app/icon.svg. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("size-8", className)} aria-hidden="true" focusable="false">
      <rect width="64" height="64" rx="14" fill="#0090ff" />
      <path d="M13 30.5 51 14 41 51 31 39.5z" fill="#fff" />
      <path d="M31 39.5 51 14 24.5 35.5z" fill="#fff" fillOpacity="0.65" />
      <path d="M31 39.5V50l5.5-6.8z" fill="#fff" fillOpacity="0.8" />
    </svg>
  );
}

/**
 * Logo forms: "full" = mark + wordmark (sidebar, login), "compact" = mark only (collapsed sidebar,
 * small screens). The wordmark uses theme tokens so one component serves light and dark.
 */
export function Logo({ variant = "full", className }: { variant?: "full" | "compact"; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LogoMark />
      {variant === "full" ? (
        <span className="text-lg font-semibold tracking-tight text-foreground">
          Career<span className="text-accent-text">Pilot</span>
        </span>
      ) : (
        <span className="sr-only">CareerPilot</span>
      )}
    </span>
  );
}

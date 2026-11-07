// Legacy shared class strings used by pages that have not been moved to the new components yet.
// They match the components in components/ui/* (same height, radius, border and hover), so an old
// page next to a new one does not look like a different product. Delete this file once every page
// uses components/ui/* (deletion pass, docs/phase-7/07-tasks.md P-group).
export const input =
  "h-[var(--control-h)] w-full rounded-md border border-input bg-surface px-3 text-[length:var(--text-base)] text-foreground " +
  "placeholder:text-muted-foreground transition-colors hover:border-foreground/40 focus-visible:border-ring";
export const select =
  "h-[var(--control-h)] rounded-md border border-input bg-surface px-2.5 text-[length:var(--text-base)] text-foreground " +
  "transition-colors hover:border-foreground/40 focus-visible:border-ring";
export const button =
  "inline-flex h-[var(--control-h)] items-center justify-center gap-2 rounded-md border border-input bg-surface px-3.5 " +
  "text-[length:var(--text-base)] font-medium text-foreground transition-colors hover:bg-surface-hover " +
  "disabled:pointer-events-none disabled:opacity-50";
export const primaryButton =
  "inline-flex h-[var(--control-h)] items-center justify-center gap-2 rounded-md bg-primary px-3.5 " +
  "text-[length:var(--text-base)] font-medium text-primary-foreground transition-colors hover:bg-primary-hover " +
  "disabled:pointer-events-none disabled:opacity-50";
export const card =
  "rounded-lg border border-border-subtle bg-surface p-[var(--pad-card)] transition-shadow duration-[var(--dur)] hover:shadow-sm";
export const muted = "text-sm text-muted-foreground";

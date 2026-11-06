// Legacy shared class strings used by pages that have not been moved to the new components yet.
// They now use the design tokens, so those pages follow the theme. Delete this file once every page
// uses components/ui/* (deletion pass, docs/phase-7/07-tasks.md P-group).
export const input =
  "w-full rounded-md border border-input bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground " +
  "hover:border-foreground/40 focus-visible:border-ring";
export const select =
  "rounded-md border border-input bg-surface px-2 py-1.5 text-sm text-foreground hover:border-foreground/40";
export const button =
  "rounded-md border border-input bg-surface px-3 py-1.5 text-sm font-medium text-foreground " +
  "transition-colors hover:bg-surface-hover disabled:opacity-50";
export const primaryButton =
  "rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground " +
  "transition-colors hover:bg-primary-hover disabled:opacity-50";
export const card = "rounded-lg border border-border-subtle bg-surface p-4";
export const muted = "text-sm text-muted-foreground";

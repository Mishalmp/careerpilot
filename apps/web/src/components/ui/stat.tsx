import { ArrowUpRight, type LucideIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { cn } from "@/lib/utils";

const tones = {
  accent: "bg-accent-soft text-accent-text",
  success: "bg-success-soft text-success-text",
  warning: "bg-warning-soft text-warning-text",
  danger: "bg-danger-soft text-danger-text",
  violet: "bg-violet-soft text-violet-text",
  neutral: "bg-surface-hover text-muted-foreground",
} as const;

export type Tone = keyof typeof tones;

/** A round icon on a tinted background: the one way to put an icon next to a number or a title. */
export function IconChip({ icon: Icon, tone = "accent", className }: { icon: LucideIcon; tone?: Tone; className?: string }) {
  return (
    <span className={cn("inline-flex size-9 shrink-0 items-center justify-center rounded-lg [&_svg]:size-[1.125rem]", tones[tone], className)}>
      <Icon aria-hidden="true" />
    </span>
  );
}

/**
 * A number with a label. With `href` the whole tile is one link that lifts on hover, so it is
 * obvious it can be opened; without it the tile is static.
 */
export function StatTile({
  label,
  value,
  hint,
  icon,
  tone = "accent",
  href,
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon: LucideIcon;
  tone?: Tone;
  href?: string;
  className?: string;
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[0.8125rem] text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tracking-tight tabular sm:text-3xl">{value}</p>
        </div>
        <IconChip icon={icon} tone={tone} className="hidden sm:inline-flex" />
      </div>
      {hint ? <p className="mt-2 pr-5 text-xs text-muted-foreground">{hint}</p> : null}
      {href ? (
        <ArrowUpRight
          className="absolute right-3 bottom-3 size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
          aria-hidden="true"
        />
      ) : null}
    </>
  );
  const base = "relative block rounded-lg border border-border-subtle bg-surface p-3.5 sm:p-[var(--pad-card)]";
  if (!href) return <div className={cn(base, className)}>{body}</div>;
  return (
    <Link
      href={href}
      className={cn(
        base,
        "group transition-[transform,box-shadow,border-color] duration-[var(--dur)] hover:-translate-y-0.5 hover:border-border hover:shadow-float focus-visible:-translate-y-0.5",
        className,
      )}
    >
      {body}
    </Link>
  );
}

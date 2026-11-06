import { AlertTriangle, CircleCheck, Info, OctagonAlert } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

import { Button } from "./button";

/** Nothing here yet: say what this is, why it is empty, and the one next step. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-lg border border-dashed border-border px-6 py-12 text-center",
        className,
      )}
    >
      {icon ? <div className="text-muted-foreground [&_svg]:size-8">{icon}</div> : null}
      <div className="flex flex-col gap-1">
        <h3 className="text-base font-semibold">{title}</h3>
        {description ? <p className="max-w-md text-sm text-muted-foreground">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

/** Something failed: plain words about what happened, a retry, no stack traces. */
export function ErrorState({
  title = "Something went wrong",
  description,
  onRetry,
  className,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-3 rounded-lg border border-danger/40 bg-danger-soft p-4 text-danger-text",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <OctagonAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div>
          <p className="font-medium">{title}</p>
          {description ? <p className="mt-0.5 text-sm">{description}</p> : null}
        </div>
      </div>
      {onRetry ? (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

const alertTones = {
  info: { box: "bg-accent-soft text-accent-text border-accent-text/30", Icon: Info },
  success: { box: "bg-success-soft text-success-text border-success-text/30", Icon: CircleCheck },
  warning: { box: "bg-warning-soft text-warning-text border-warning-text/30", Icon: AlertTriangle },
  danger: { box: "bg-danger-soft text-danger-text border-danger-text/30", Icon: OctagonAlert },
} as const;

/** Inline notice. Icon + text + colour, so meaning never depends on colour alone. */
export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: keyof typeof alertTones;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { box, Icon } = alertTones[tone];
  return (
    <div
      role={tone === "danger" || tone === "warning" ? "alert" : "status"}
      className={cn("flex gap-2 rounded-lg border p-3 text-sm", box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div>
        {title ? <p className="font-medium">{title}</p> : null}
        {children ? <div className={title ? "mt-0.5" : undefined}>{children}</div> : null}
      </div>
    </div>
  );
}

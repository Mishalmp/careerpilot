"use client";

import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, CircleMinus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { api, unwrap } from "@/lib/api/client";

type Tone = "success" | "warning" | "danger" | "neutral";

/** Every state is an icon plus words plus colour, so it never relies on colour alone. */
function State({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  const Icon =
    tone === "success"
      ? CircleCheck
      : tone === "neutral"
        ? CircleMinus
        : CircleAlert;
  return (
    <Badge tone={tone}>
      <Icon aria-hidden="true" /> {children}
    </Badge>
  );
}

function ago(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "never";
  const minutes = Math.round((now - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 60 * 48) return `${Math.round(minutes / 60)} h ago`;
  return `${Math.round(minutes / 1440)} days ago`;
}

export function StatusPanel() {
  const status = useQuery({
    queryKey: ["system", "status"],
    queryFn: async () => unwrap(await api.GET("/api/v1/system/status")),
    refetchInterval: 15_000, // the numbers change, so keep them fresh while the tab is open
  });

  if (status.isPending)
    return (
      <Skeleton className="h-64" aria-busy="true" aria-label="Loading status" />
    );
  if (status.isError) {
    return (
      <ErrorState
        title="Could not read the system status"
        description={status.error.message}
        onRetry={() => void status.refetch()}
      />
    );
  }
  const s = status.data;
  const capUsed = s.ai.daily_cap
    ? Math.round((100 * s.ai.tokens_today) / s.ai.daily_cap)
    : 0;
  const backupWarn =
    !s.backups.key_set ||
    s.backups.age_hours == null ||
    s.backups.age_hours > 48;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Checked {ago(s.checked_at)}; updates every 15 seconds. Secrets are never
        shown here.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Database</CardTitle>
            <CardDescription>Where all your data lives</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div>
              <State tone={s.database.ok ? "success" : "danger"}>
                {s.database.ok ? "Connected" : "Not reachable"}
              </State>
            </div>
            <p className="text-muted-foreground">
              Schema version{" "}
              <code className="rounded bg-surface-hover px-1.5 py-0.5 text-xs">
                {s.database.revision ?? "unknown"}
              </code>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Background tasks</CardTitle>
            <CardDescription>Work done by the worker</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div className="flex flex-wrap gap-2">
              <State tone={s.tasks.failed > 0 ? "danger" : "success"}>
                {s.tasks.failed} failed
              </State>
              <State tone={s.tasks.queued > 0 ? "warning" : "neutral"}>
                {s.tasks.queued} waiting
              </State>
              <State tone="neutral">{s.tasks.running} running</State>
            </div>
            <p className="text-muted-foreground">
              Last task finished {ago(s.last_task_finished_at)}.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI use today</CardTitle>
            <CardDescription>Model calls are capped per day</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <div>
              <State tone={s.ai.configured ? "success" : "warning"}>
                {s.ai.configured
                  ? "API key set"
                  : "No API key: AI features are off"}
              </State>
            </div>
            <div
              className="h-1.5 overflow-hidden rounded-full bg-surface-hover"
              role="img"
              aria-label={`${capUsed} percent of the daily cap used`}
            >
              <div
                className={
                  capUsed >= 90 ? "h-full bg-danger" : "h-full bg-primary"
                }
                style={{ width: `${Math.min(100, Math.max(1, capUsed))}%` }}
              />
            </div>
            <p className="tabular text-muted-foreground">
              {s.ai.tokens_today.toLocaleString()} of{" "}
              {s.ai.daily_cap.toLocaleString()} tokens ({capUsed}%)
            </p>
            <p className="tabular text-muted-foreground">
              ${s.ai.spent_month_usd.toFixed(2)} of $
              {s.ai.monthly_budget_usd.toFixed(2)} this month; $
              {s.ai.spent_today_usd.toFixed(2)} of $
              {s.ai.daily_budget_usd.toFixed(2)} today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Search and backups</CardTitle>
            <CardDescription>
              Research search service and your safety net
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-start gap-2 text-sm">
            <State tone={s.search.configured ? "success" : "neutral"}>
              {s.search.configured
                ? `Search: ${s.search.provider}`
                : "Search not set up (manual paste only)"}
            </State>
            <State tone={backupWarn ? "warning" : "success"}>
              {!s.backups.key_set
                ? "No backup key: nothing is backed up"
                : s.backups.last_backup_at
                  ? `Last backup ${ago(s.backups.last_backup_at)}`
                  : "Key set, no backup made yet"}
            </State>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

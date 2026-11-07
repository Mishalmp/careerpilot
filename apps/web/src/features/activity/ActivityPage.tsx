"use client";

import {
  CalendarCheck,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Clock,
  Cpu,
  DatabaseBackup,
  FlaskConical,
  Info,
  ListChecks,
  Loader2,
  Radar,
  RotateCw,
  TriangleAlert,
  X,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { ProgressBar } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { IconChip, StatTile, type Tone } from "@/components/ui/stat";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

import { type AiCall, type Task, type TaskStatus, useAiCalls, useCancelTask, useRetryFailed, useRetryTask, useTask, useTasks } from "./hooks";

const KIND: Record<Task["kind"], { label: string; icon: LucideIcon; tone: Tone }> = {
  discover: { label: "Read a job board", icon: Radar, tone: "accent" },
  daily_digest: { label: "Build the daily digest", icon: CalendarCheck, tone: "violet" },
  backup: { label: "Back up the database", icon: DatabaseBackup, tone: "neutral" },
  research: { label: "Research interview topics", icon: FlaskConical, tone: "warning" },
  apply_queue: { label: "Build the daily apply list", icon: ListChecks, tone: "success" },
};
const STATUS: Record<TaskStatus, { label: string; tone: "neutral" | "accent" | "success" | "danger" }> = {
  queued: { label: "Waiting", tone: "neutral" },
  running: { label: "Running", tone: "accent" },
  succeeded: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

/** "2 min ago" for recent times, a date for old ones. */
export function ago(iso: string, now = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`;
  return new Date(iso).toLocaleDateString();
}

export function ActivityPage() {
  const [filter, setFilter] = useState<TaskStatus | "all">("all");
  const tasks = useTasks(filter === "all" ? undefined : filter);
  const counts = tasks.data?.counts;
  const retryAll = useRetryFailed();

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Activity"
        description="Everything the app does in the background, step by step: tasks, what each attempt did, and every AI call. A failed task can be retried here and continues from where it stopped."
        actions={
          counts && counts.failed > 0 ? (
            <Button variant="primary" onClick={() => retryAll.mutate()} loading={retryAll.isPending}>
              <RotateCw aria-hidden="true" /> Retry all failed ({counts.failed})
            </Button>
          ) : undefined
        }
      />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(["queued", "running", "succeeded", "failed"] as const).map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={filter === s}
            onClick={() => setFilter(filter === s ? "all" : s)}
            className={cn("rounded-lg text-left transition-shadow", filter === s && "ring-2 ring-primary")}
          >
            <StatTile
              label={STATUS[s].label}
              value={counts ? counts[s] : "-"}
              icon={s === "failed" ? CircleAlert : s === "running" ? Loader2 : s === "succeeded" ? CheckCircle2 : Clock}
              tone={s === "failed" ? "danger" : s === "running" ? "accent" : s === "succeeded" ? "success" : "neutral"}
            />
          </button>
        ))}
      </div>

      <Tabs defaultValue="tasks">
        <TabsList>
          <TabsTrigger value="tasks">Background tasks</TabsTrigger>
          <TabsTrigger value="ai">AI calls</TabsTrigger>
        </TabsList>
        <TabsContent value="tasks">
          {tasks.isPending && <Skeleton className="h-32" aria-busy="true" aria-label="Loading tasks" />}
          {tasks.isError && <ErrorState title="Could not load tasks" description={tasks.error.message} onRetry={() => void tasks.refetch()} />}
          {tasks.data && tasks.data.items.length === 0 && (
            <EmptyState
              icon={<ListChecks aria-hidden="true" />}
              title={filter === "all" ? "No background work yet" : "Nothing here"}
              description={filter === "all" ? "Job boards, the digest, the daily apply list, research runs and backups show up here as they run." : "No task has this status."}
            />
          )}
          {retryAll.error && (
            <p role="alert" className="mb-2 text-sm text-danger-text">
              {retryAll.error.message}
            </p>
          )}
          <ul className="flex flex-col gap-3">
            {tasks.data?.items.map((t) => (
              <TaskCard key={t.id} task={t} />
            ))}
          </ul>
        </TabsContent>
        <TabsContent value="ai">
          <AiCalls />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function TaskCard({ task }: { task: Task }) {
  const [open, setOpen] = useState(task.status === "failed");
  const retry = useRetryTask();
  const cancel = useCancelTask();
  const kind = KIND[task.kind];
  const progress = task.progress;
  const pct = progress?.total ? ((progress.done ?? 0) / progress.total) * 100 : null;
  const error = retry.error ?? cancel.error;
  return (
    <li className="rounded-lg border border-border-subtle bg-surface p-4" aria-label={kind.label}>
      <div className="flex flex-wrap items-start gap-3">
        <IconChip icon={kind.icon} tone={kind.tone} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium">{kind.label}</h3>
            <Badge tone={STATUS[task.status].tone}>
              {task.status === "running" && <Loader2 className="animate-spin" aria-hidden="true" />}
              {STATUS[task.status].label}
            </Badge>
            <span className="text-xs text-muted-foreground">
              attempt {task.attempts} of {task.max_attempts} · {ago(task.created_at)}
            </span>
          </div>
          {task.status === "running" && (
            <div className="mt-2 flex max-w-md flex-col gap-1">
              <ProgressBar label={`${kind.label} progress`} value={pct} />
              <p className="text-xs text-muted-foreground" role="status">
                {progress?.step ?? "Starting"}
              </p>
            </div>
          )}
          {task.status === "queued" && task.attempts > 0 && <p className="mt-1 text-xs text-muted-foreground">Next try at {new Date(task.run_after).toLocaleTimeString()}.</p>}
          {task.error && task.status !== "succeeded" && (
            <p className="mt-2 flex items-start gap-1.5 text-sm text-danger-text">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" /> {task.error}
            </p>
          )}
          {task.status === "failed" && progress && <p className="mt-1 text-xs text-muted-foreground">Stopped at: {progress.step}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {task.status === "failed" && task.error !== "Cancelled by you." && (
            <Button size="sm" variant="primary" onClick={() => retry.mutate(task.id)} loading={retry.isPending} aria-label={`Retry: ${kind.label}`}>
              <RotateCw aria-hidden="true" /> Retry
            </Button>
          )}
          {task.status === "failed" && task.error === "Cancelled by you." && (
            <Button size="sm" onClick={() => retry.mutate(task.id)} loading={retry.isPending} aria-label={`Run again: ${kind.label}`}>
              <RotateCw aria-hidden="true" /> Run again
            </Button>
          )}
          {task.status === "queued" && (
            <Button size="sm" onClick={() => cancel.mutate(task.id)} loading={cancel.isPending} aria-label={`Cancel: ${kind.label}`}>
              <X aria-hidden="true" /> Cancel
            </Button>
          )}
          <Button size="sm" variant="ghost" aria-expanded={open} aria-label={`${open ? "Hide" : "Show"} history: ${kind.label}`} onClick={() => setOpen((o) => !o)}>
            History <ChevronDown className={cn("transition-transform", open && "rotate-180")} aria-hidden="true" />
          </Button>
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-danger-text">
          {error.message}
        </p>
      )}
      {open && <History id={task.id} />}
    </li>
  );
}

const EVENT_ICON = {
  info: { Icon: Info, cls: "text-muted-foreground" },
  warning: { Icon: TriangleAlert, cls: "text-warning-text" },
  error: { Icon: CircleAlert, cls: "text-danger-text" },
} as const;

function History({ id }: { id: string }) {
  const detail = useTask(id, true);
  if (detail.isPending) return <Skeleton className="mt-3 h-16" aria-busy="true" aria-label="Loading history" />;
  if (detail.isError) return <p role="alert" className="mt-3 text-sm text-danger-text">{detail.error.message}</p>;
  return (
    <ol className="mt-3 flex flex-col gap-1.5 border-l-2 border-border-subtle pl-4" aria-label="History">
      {detail.data.events.map((e) => {
        const { Icon, cls } = EVENT_ICON[e.level as keyof typeof EVENT_ICON] ?? EVENT_ICON.info;
        return (
          <li key={e.id} className="flex items-start gap-2 text-sm">
            <Icon className={cn("mt-0.5 size-3.5 shrink-0", cls)} aria-hidden="true" />
            <span className="min-w-0 flex-1">{e.message}</span>
            <span className="shrink-0 text-xs text-muted-foreground tabular">
              {e.attempt > 0 ? `#${e.attempt} · ` : ""}
              {new Date(e.at).toLocaleTimeString()}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function AiCalls() {
  const [problems, setProblems] = useState(false);
  const calls = useAiCalls(problems);
  if (calls.isPending) return <Skeleton className="h-32" aria-busy="true" aria-label="Loading AI calls" />;
  if (calls.isError) return <ErrorState title="Could not load AI calls" description={calls.error.message} onRetry={() => void calls.refetch()} />;
  const { tokens_today: used, daily_cap: cap, items } = calls.data;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 rounded-lg border border-border-subtle bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <IconChip icon={Cpu} tone="violet" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">
              {used.toLocaleString()} of {cap.toLocaleString()} tokens used today
            </p>
            <ProgressBar label="Daily AI token budget" value={cap ? (used / cap) * 100 : 0} className="mt-1.5 max-w-sm" />
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={problems} onCheckedChange={setProblems} aria-label="Only problems" />
          Only problems
        </label>
      </div>
      {items.length === 0 ? (
        <EmptyState
          icon={<Cpu aria-hidden="true" />}
          title={problems ? "No problems" : "No AI calls yet"}
          description="Prompts and answers are never stored: only which feature asked, the model, the tokens and the time."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border-subtle bg-surface">
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left text-xs text-muted-foreground">
                <th className="px-4 py-2 font-medium">When</th>
                <th className="px-4 py-2 font-medium">Feature</th>
                <th className="px-4 py-2 font-medium">Model</th>
                <th className="px-4 py-2 text-right font-medium">Tokens in / out</th>
                <th className="px-4 py-2 text-right font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <CallRow key={c.id} call={c} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CallRow({ call }: { call: AiCall }) {
  return (
    <tr className="border-b border-border-subtle last:border-0 hover:bg-surface-muted">
      <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{ago(call.created_at)}</td>
      <td className="px-4 py-2 font-medium">{call.purpose}</td>
      <td className="px-4 py-2 text-muted-foreground">{call.model}</td>
      <td className="px-4 py-2 text-right tabular">
        {call.input_tokens.toLocaleString()} / {call.output_tokens.toLocaleString()}
      </td>
      <td className="px-4 py-2 text-right tabular">{(call.latency_ms / 1000).toFixed(1)} s</td>
      <td className="px-4 py-2">
        <Badge tone={call.status === "ok" ? "success" : "danger"}>{call.status}</Badge>
        {call.error ? <span className="ml-2 text-xs text-danger-text">{call.error}</span> : null}
      </td>
    </tr>
  );
}

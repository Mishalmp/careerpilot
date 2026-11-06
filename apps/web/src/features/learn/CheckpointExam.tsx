"use client";

import { ChevronLeft, ChevronRight, CircleAlert, CircleCheck, Flag, Timer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

import { type Checkpoint, type CheckpointItem, useCheckpoint, useSaveItem, useSubmitCheckpoint } from "./checkpointHooks";

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function CheckpointExam() {
  const { id } = useParams<{ id: string }>();
  const query = useCheckpoint(id);

  if (query.isPending) return <Skeleton className="h-96" aria-busy="true" aria-label="Loading checkpoint" />;
  if (query.isError) {
    return (
      <div className="flex flex-col gap-3">
        <ErrorState title="Could not open this checkpoint" description={query.error.message} />
        <Link href="/learn/checkpoints" className="text-sm text-accent-text underline">
          Back to checkpoints
        </Link>
      </div>
    );
  }
  return query.data.status === "submitted" ? <Report cp={query.data} /> : <Exam cp={query.data} />;
}

function Exam({ cp }: { cp: Checkpoint }) {
  const save = useSaveItem(cp.id);
  const submit = useSubmitCheckpoint(cp.id);
  const [index, setIndex] = useState(0);
  const [confirm, setConfirm] = useState(false);
  // Optimistic copy of what was clicked, so the screen reacts at once. The server's saved answers
  // replace it when they arrive; if saving fails the entry is removed and the saved value shows.
  const [pending, setPending] = useState<Record<number, { selected?: number[]; flagged?: boolean }>>({});
  const deadline = new Date(cp.deadline).getTime();
  const [left, setLeft] = useState(() => Math.max(0, Math.round((deadline - Date.now()) / 1000)));

  // The clock is only a display: the server decides when time is up. When it reaches zero we
  // submit, and the server scores whatever was saved.
  useEffect(() => {
    const timer = setInterval(() => setLeft(Math.max(0, Math.round((deadline - Date.now()) / 1000))), 1000);
    return () => clearInterval(timer);
  }, [deadline]);
  useEffect(() => {
    if (left === 0 && !submit.isPending && !submit.isSuccess) submit.mutate();
  }, [left, submit]);

  const view = (i: CheckpointItem): CheckpointItem => ({ ...i, ...pending[i.position] });
  const item = view(cp.items[index]);
  const single = item.question.type === "mcq_single";
  const unanswered = cp.items.filter((i) => (view(i).selected?.length ?? 0) === 0).length;

  function change(change: { selected?: number[]; flagged?: boolean }) {
    const position = item.position;
    setPending((p) => ({ ...p, [position]: { ...p[position], ...change } }));
    save.mutate(
      { position, ...change },
      {
        onSettled: () =>
          setPending((p) => {
            const rest = { ...p };
            delete rest[position];
            return rest;
          }),
      },
    );
  }

  function choose(position: number) {
    const current = item.selected ?? [];
    const next = single ? [position] : current.includes(position) ? current.filter((p) => p !== position) : [...current, position];
    change({ selected: next });
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
      <PageHeader
        title="Checkpoint"
        description={`Question ${index + 1} of ${cp.items.length}`}
        actions={
          <span
            role="timer"
            aria-label={`Time left ${clock(left)}`}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium tabular",
              left <= 60 ? "border-danger text-danger-text" : "border-border",
            )}
          >
            <Timer className="size-4" aria-hidden="true" /> {clock(left)}
          </span>
        }
      />

      <nav aria-label="Questions" className="flex flex-wrap gap-1.5">
        {cp.items.map(view).map((i, n) => {
          const answered = (i.selected?.length ?? 0) > 0;
          return (
            <button
              key={i.position}
              type="button"
              onClick={() => setIndex(n)}
              aria-label={`Question ${n + 1}${answered ? ", answered" : ", not answered"}${i.flagged ? ", flagged" : ""}`}
              aria-current={n === index ? "step" : undefined}
              className={cn(
                "relative size-8 rounded-md border text-sm tabular transition-colors",
                n === index ? "border-primary bg-primary text-primary-foreground" : answered ? "border-primary/50 bg-accent-soft text-accent-text" : "border-border",
              )}
            >
              {n + 1}
              {i.flagged && <Flag className="absolute -right-1 -top-1 size-3 fill-warning text-warning-text" aria-hidden="true" />}
            </button>
          );
        })}
      </nav>

      <Card>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone="accent">{item.question.topic_title}</Badge>
            <Badge tone="outline">{single ? "Choose one" : "Choose every correct answer"}</Badge>
          </div>
          <h2 className="text-lg font-semibold leading-snug">{item.question.stem}</h2>
          <fieldset className="flex flex-col gap-2">
            <legend className="sr-only">{single ? "Choose one answer" : "Choose every correct answer"}</legend>
            {item.question.options.map((option) => {
              const checked = item.selected?.includes(option.position) ?? false;
              return (
                <label
                  key={option.position}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
                    checked ? "border-primary bg-accent-soft" : "border-border hover:bg-surface-muted",
                  )}
                >
                  <input
                    type={single ? "radio" : "checkbox"}
                    name={`q-${item.position}`}
                    checked={checked}
                    onChange={() => choose(option.position)}
                    className="mt-1 size-4 accent-[var(--primary)]"
                  />
                  <span className="text-[length:var(--text-base)]">{option.text}</span>
                </label>
              );
            })}
          </fieldset>
          {save.error && (
            <p role="alert" className="text-sm text-danger-text">
              Could not save your answer: {save.error.message}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={() => setIndex((i) => Math.max(0, i - 1))} disabled={index === 0}>
              <ChevronLeft aria-hidden="true" /> Previous
            </Button>
            <Button size="sm" onClick={() => setIndex((i) => Math.min(cp.items.length - 1, i + 1))} disabled={index === cp.items.length - 1}>
              Next <ChevronRight aria-hidden="true" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-pressed={item.flagged}
              onClick={() => change({ flagged: !item.flagged })}
            >
              <Flag aria-hidden="true" /> {item.flagged ? "Unflag" : "Flag for review"}
            </Button>
            <Button size="sm" variant="primary" className="ml-auto" onClick={() => setConfirm(true)}>
              Submit
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Submit your answers?</DialogTitle>
            <DialogDescription>
              {unanswered > 0
                ? `${unanswered} question${unanswered === 1 ? " is" : "s are"} unanswered and will count as wrong.`
                : "All questions are answered."}{" "}
              You cannot change answers after submitting.
            </DialogDescription>
          </DialogHeader>
          {submit.error && (
            <p role="alert" className="text-sm text-danger-text">
              {submit.error.message}
            </p>
          )}
          <DialogFooter>
            <Button onClick={() => setConfirm(false)}>Keep working</Button>
            <Button variant="primary" loading={submit.isPending} onClick={() => submit.mutate()}>
              Submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Report({ cp }: { cp: Checkpoint }) {
  const pct = Math.round((cp.score ?? 0) * 100);
  const missed = cp.items.filter((i) => !i.result?.correct);
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      <Link href="/learn/checkpoints" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="size-4" aria-hidden="true" /> Checkpoints
      </Link>
      <PageHeader title="Checkpoint result" description={cp.expired ? "Time ran out, so your saved answers were scored." : undefined} />

      <Card>
        <CardContent className="flex flex-wrap items-center gap-6">
          <div>
            <p className="text-4xl font-semibold tracking-tight tabular">{pct}%</p>
            <p className="text-sm text-muted-foreground">Pass mark {Math.round(cp.pass_mark * 100)}%</p>
          </div>
          <Badge tone={cp.passed ? "success" : "danger"} className="text-sm">
            {cp.passed ? <CircleCheck aria-hidden="true" /> : <CircleAlert aria-hidden="true" />}
            {cp.passed ? "Passed" : "Not passed yet"}
          </Badge>
          <p className="text-sm text-muted-foreground">
            {cp.items.length - missed.length} of {cp.items.length} right
          </p>
        </CardContent>
      </Card>

      {cp.per_topic && (
        <section aria-labelledby="topics-result" className="flex flex-col gap-2">
          <h2 id="topics-result" className="text-lg font-semibold tracking-tight">
            By topic
          </h2>
          <ul className="flex flex-col gap-2">
            {[...cp.per_topic]
              .sort((a, b) => a.score - b.score)
              .map((t) => (
                <li key={t.topic} className="flex items-center gap-3 rounded-lg border border-border-subtle bg-surface p-3">
                  <span className="min-w-0 flex-1 truncate font-medium">{t.topic}</span>
                  <div className="h-1.5 w-28 overflow-hidden rounded-full bg-surface-hover" aria-hidden="true">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(2, t.score * 100)}%` }} />
                  </div>
                  <span className="tabular w-24 text-right text-sm text-muted-foreground">
                    {t.correct}/{t.total} · {Math.round(t.score * 100)}%
                  </span>
                </li>
              ))}
          </ul>
        </section>
      )}

      {missed.length > 0 && (
        <p className="rounded-lg bg-accent-soft p-3 text-sm text-accent-text">
          The {missed.length} question{missed.length === 1 ? "" : "s"} you missed are due for review now.{" "}
          <Link href="/learn/review" className="font-medium underline">
            Start review
          </Link>
        </p>
      )}

      <section aria-labelledby="answers-heading" className="flex flex-col gap-3">
        <h2 id="answers-heading" className="text-lg font-semibold tracking-tight">
          Your answers
        </h2>
        <ul className="flex flex-col gap-3">
          {cp.items.map((i) => (
            <ResultRow key={i.position} item={i} />
          ))}
        </ul>
      </section>
    </div>
  );
}

function ResultRow({ item }: { item: CheckpointItem }) {
  const r = item.result;
  if (!r) return null;
  const picked = item.selected ?? [];
  return (
    <li className="rounded-lg border border-border-subtle bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={r.correct ? "success" : "danger"}>
          {r.correct ? <CircleCheck aria-hidden="true" /> : <CircleAlert aria-hidden="true" />}
          {r.correct ? "Right" : picked.length === 0 ? "Not answered" : r.score > 0 ? "Partly right" : "Wrong"}
        </Badge>
        <Badge tone="outline">{item.question.topic_title}</Badge>
      </div>
      <p className="mt-2 font-medium">{item.question.stem}</p>
      <ul className="mt-2 flex flex-col gap-1.5 text-sm">
        {r.options.map((o) => {
          const wasPicked = picked.includes(o.position);
          return (
            <li
              key={o.position}
              className={cn(
                "rounded-md border px-3 py-1.5",
                o.is_correct ? "border-success bg-success-soft" : wasPicked ? "border-danger bg-danger-soft" : "border-border-subtle",
              )}
            >
              {o.text}
              {o.is_correct && <span className="ml-2 font-medium text-success-text">Correct</span>}
              {wasPicked && !o.is_correct && <span className="ml-2 font-medium text-danger-text">Your pick</span>}
              {wasPicked && o.is_correct && <span className="ml-2 text-muted-foreground">(you picked this)</span>}
              {o.rationale && <span className="mt-0.5 block text-xs text-muted-foreground">{o.rationale}</span>}
            </li>
          );
        })}
      </ul>
      {r.explanation && <p className="mt-2 text-sm">{r.explanation}</p>}
    </li>
  );
}

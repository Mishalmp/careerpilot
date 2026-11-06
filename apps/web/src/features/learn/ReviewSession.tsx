"use client";

import { ArrowRight, Check, CheckCircle2, CircleAlert, ExternalLink, PartyPopper, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { cn } from "@/lib/utils";

import { type AnswerResult, type QuestionToAnswer, typeLabel, useAnswer, useReviewQueue } from "./hooks";

const CONFIDENCE = [
  { value: 1, label: "Guessing" },
  { value: 2, label: "Think so" },
  { value: 3, label: "Sure" },
] as const;

const SELF_RATINGS = [
  { score: 0, label: "Missed it" },
  { score: 0.5, label: "Partly" },
  { score: 1, label: "Got it" },
] as const;

type Tally = { answered: number; correct: number };

/** "in 10 minutes", "in 3 days": when the question comes back. */
export function whenDue(iso: string, now = Date.now()): string {
  const minutes = Math.max(1, Math.round((new Date(iso).getTime() - now) / 60_000));
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "always" });
  if (minutes < 60) return rtf.format(minutes, "minute");
  if (minutes < 60 * 24) return rtf.format(Math.round(minutes / 60), "hour");
  return rtf.format(Math.round(minutes / (60 * 24)), "day");
}

export function ReviewSession() {
  const queue = useReviewQueue(20);
  const [index, setIndex] = useState(0);
  const [tally, setTally] = useState<Tally>({ answered: 0, correct: 0 });

  if (queue.isPending || queue.isFetching) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4" aria-busy="true" aria-label="Loading questions">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (queue.isError) {
    return <ErrorState title="Could not load your review" description={queue.error.message} onRetry={() => void queue.refetch()} />;
  }
  const items = queue.data.items;
  if (items.length === 0) {
    return (
      <EmptyState
        icon={<PartyPopper aria-hidden="true" />}
        title="You are all caught up"
        description="Nothing is due and today's allowance of new questions is used. Add more questions, or come back later."
        action={
          <Button asChild variant="primary">
            <Link href="/learn">Back to Learn</Link>
          </Button>
        }
      />
    );
  }
  if (index >= items.length) {
    return (
      <Summary
        tally={tally}
        total={items.length}
        onRestart={() => {
          setIndex(0);
          setTally({ answered: 0, correct: 0 });
          void queue.refetch();
        }}
      />
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-5">
      <PageHeader title="Review" description={`${queue.data.due} due · ${queue.data.new_available} new available today`} />
      <div
        role="progressbar"
        aria-label="Progress"
        aria-valuemin={0}
        aria-valuemax={items.length}
        aria-valuenow={index}
        aria-valuetext={`Question ${index + 1} of ${items.length}`}
        className="flex items-center gap-3"
      >
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-hover">
          <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${(index / items.length) * 100}%` }} />
        </div>
        <span className="tabular text-xs text-muted-foreground">
          {index + 1} / {items.length}
        </span>
      </div>
      <QuestionCard
        key={items[index].id}
        question={items[index]}
        isLast={index === items.length - 1}
        onNext={(correct) => {
          setTally((t) => ({ answered: t.answered + 1, correct: t.correct + (correct ? 1 : 0) }));
          setIndex((i) => i + 1);
        }}
      />
    </div>
  );
}

function Summary({ tally, total, onRestart }: { tally: Tally; total: number; onRestart: () => void }) {
  const pct = tally.answered ? Math.round((100 * tally.correct) / tally.answered) : 0;
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <PageHeader title="Session complete" description="Your next reviews are scheduled automatically." />
      <Card>
        <CardContent className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-3xl font-semibold tracking-tight">{total}</p>
            <p className="text-xs text-muted-foreground">Answered</p>
          </div>
          <div>
            <p className="text-3xl font-semibold tracking-tight">{tally.correct}</p>
            <p className="text-xs text-muted-foreground">Right</p>
          </div>
          <div>
            <p className="text-3xl font-semibold tracking-tight">{pct}%</p>
            <p className="text-xs text-muted-foreground">Accuracy</p>
          </div>
        </CardContent>
      </Card>
      <div className="flex gap-2">
        <Button asChild variant="primary">
          <Link href="/learn">Back to Learn</Link>
        </Button>
        <Button onClick={onRestart}>Review more</Button>
      </div>
    </div>
  );
}

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.tagName === "TEXTAREA" || (target.tagName === "INPUT" && (target as HTMLInputElement).type === "text");
}

function QuestionCard({
  question,
  isLast,
  onNext,
}: {
  question: QuestionToAnswer;
  isLast: boolean;
  onNext: (correct: boolean) => void;
}) {
  const answer = useAnswer();
  const token = useMemo(() => crypto.randomUUID(), []);
  const startedAt = useRef(0);
  const [selected, setSelected] = useState<number[]>([]);
  const [text, setText] = useState("");
  const [confidence, setConfidence] = useState<number>(2);
  const [result, setResult] = useState<AnswerResult | null>(null);

  const isChoice = question.type === "mcq_single" || question.type === "mcq_multi";
  const single = question.type === "mcq_single";

  useEffect(() => {
    startedAt.current = performance.now();
  }, []);

  const submit = useCallback(
    (selfScore?: number) => {
      if (answer.isPending || result) return;
      answer.mutate(
        {
          questionId: question.id,
          token,
          selected: isChoice ? selected : undefined,
          text: !isChoice ? text : undefined,
          selfScore,
          confidence,
          seconds: Math.round((performance.now() - startedAt.current) / 100) / 10,
        },
        { onSuccess: setResult },
      );
    },
    [answer, result, question.id, token, isChoice, selected, text, confidence],
  );

  function toggle(position: number) {
    if (result) return;
    setSelected((current) =>
      single ? [position] : current.includes(position) ? current.filter((p) => p !== position) : [...current, position],
    );
  }

  // Keyboard: 1-5 pick an option, Enter checks the answer, then Enter moves on.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (result) {
        if (event.key === "Enter") {
          event.preventDefault();
          onNext(result.correct);
        }
        return;
      }
      if (isTyping(event.target)) return;
      if (isChoice && /^[1-5]$/.test(event.key)) {
        const option = question.options[Number(event.key) - 1];
        if (option) toggle(option.position);
      } else if (isChoice && event.key === "Enter" && selected.length > 0) {
        event.preventDefault();
        submit();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <Card>
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="accent">{question.topic_title}</Badge>
          <Badge tone="outline">{typeLabel(question.type)}</Badge>
          {question.is_new && <Badge tone="success">New</Badge>}
          {question.status !== "verified" && <Badge tone="warning">Check this yourself</Badge>}
        </div>

        <h2 className="text-lg font-semibold leading-snug">{question.stem}</h2>

        {isChoice ? (
          <fieldset className="flex flex-col gap-2" disabled={Boolean(result)}>
            <legend className="sr-only">{single ? "Choose one answer" : "Choose every correct answer"}</legend>
            {question.options.map((option, i) => {
              const checked = selected.includes(option.position);
              const revealedCorrect = result?.correct_positions.includes(option.position);
              const wrongPick = result && checked && !revealedCorrect;
              const rationale = result?.options.find((o) => o.position === option.position)?.rationale;
              return (
                <label
                  key={option.position}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors",
                    "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
                    !result && (checked ? "border-primary bg-accent-soft" : "border-border hover:bg-surface-muted"),
                    revealedCorrect && "border-success bg-success-soft",
                    wrongPick && "border-danger bg-danger-soft",
                    result && !revealedCorrect && !wrongPick && "border-border-subtle opacity-70",
                  )}
                >
                  <input
                    type={single ? "radio" : "checkbox"}
                    name="answer"
                    checked={checked}
                    onChange={() => toggle(option.position)}
                    className="mt-1 size-4 accent-[var(--primary)]"
                  />
                  <span className="flex-1">
                    <span className="text-[length:var(--text-base)]">{option.text}</span>
                    {result && rationale ? (
                      <span className="mt-1 block text-xs text-muted-foreground">{rationale}</span>
                    ) : null}
                  </span>
                  {result && revealedCorrect ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-success-text">
                      <Check className="size-3.5" aria-hidden="true" /> Correct
                    </span>
                  ) : null}
                  {wrongPick ? (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-danger-text">
                      <X className="size-3.5" aria-hidden="true" /> Your pick
                    </span>
                  ) : null}
                  {!result && <kbd className="rounded border border-border px-1.5 text-xs text-muted-foreground">{i + 1}</kbd>}
                </label>
              );
            })}
          </fieldset>
        ) : (
          <div className="flex flex-col gap-3">
            <Textarea
              aria-label="Your answer"
              rows={6}
              placeholder="Write your answer first, then check it against the marking points."
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={Boolean(result)}
            />
            {question.rubric && question.rubric.length > 0 && (
              <details className="rounded-md border border-border-subtle p-3 text-sm">
                <summary className="cursor-pointer font-medium">Marking points (after you have written your answer)</summary>
                <ul className="mt-2 list-inside list-disc text-muted-foreground">
                  {question.rubric.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        {!result && (
          <>
            <fieldset className="flex flex-wrap items-center gap-2">
              <legend className="mb-1 text-[0.8125rem] font-medium">How sure are you?</legend>
              {CONFIDENCE.map((c) => (
                <label
                  key={c.value}
                  className={cn(
                    "cursor-pointer rounded-full border px-3 py-1 text-[0.8125rem] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
                    confidence === c.value ? "border-primary bg-accent-soft text-accent-text" : "border-border text-muted-foreground",
                  )}
                >
                  <input
                    type="radio"
                    name="confidence"
                    className="sr-only"
                    checked={confidence === c.value}
                    onChange={() => setConfidence(c.value)}
                  />
                  {c.label}
                </label>
              ))}
            </fieldset>

            {answer.error && (
              <p role="alert" className="text-sm text-danger-text">
                {answer.error.message}
              </p>
            )}

            {isChoice ? (
              <div>
                <Button variant="primary" disabled={selected.length === 0} loading={answer.isPending} onClick={() => submit()}>
                  Check answer <kbd className="ml-1 hidden text-xs opacity-80 sm:inline">Enter</kbd>
                </Button>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-muted-foreground">How did you do?</span>
                {SELF_RATINGS.map((r) => (
                  <Button key={r.score} loading={answer.isPending} disabled={!text.trim()} onClick={() => submit(r.score)}>
                    {r.label}
                  </Button>
                ))}
              </div>
            )}
          </>
        )}

        {result && <Reveal result={result} />}

        {result && (
          <div>
            <Button variant="primary" onClick={() => onNext(result.correct)} autoFocus>
              {isLast ? "Finish" : "Next"} <ArrowRight aria-hidden="true" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Reveal({ result }: { result: AnswerResult }) {
  const partial = !result.correct && result.score > 0;
  return (
    <div className="flex flex-col gap-3" role="status">
      <div className="flex flex-wrap items-center gap-2">
        {result.correct ? (
          <Badge tone="success">
            <CheckCircle2 aria-hidden="true" /> Correct
          </Badge>
        ) : partial ? (
          <Badge tone="warning">
            <CircleAlert aria-hidden="true" /> Partly right ({Math.round(result.score * 100)}%)
          </Badge>
        ) : (
          <Badge tone="danger">
            <CircleAlert aria-hidden="true" /> Not quite
          </Badge>
        )}
        <span className="text-xs text-muted-foreground">
          {result.graded_by === "self" ? "Rated by you" : "Marked automatically"} · back {whenDue(result.next_due)}
        </span>
      </div>
      {result.explanation && <p className="text-[length:var(--text-base)]">{result.explanation}</p>}
      {result.sources.length > 0 && (
        <ul className="flex flex-col gap-1.5 text-sm">
          {result.sources.map((s) => (
            <li key={s.url} className="rounded-md bg-surface-muted p-2">
              <blockquote className="text-muted-foreground">“{s.quote}”</blockquote>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-accent-text underline underline-offset-2"
              >
                {s.title ?? s.url} <ExternalLink className="size-3" aria-hidden="true" />
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

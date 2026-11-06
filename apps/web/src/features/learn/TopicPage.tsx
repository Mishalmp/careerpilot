"use client";

import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";

import {
  type LearnQuestion,
  typeLabel,
  useDeleteQuestion,
  useDeleteTopic,
  useLearnQuestions,
  useLearnTopics,
  useUpdateTopic,
} from "./hooks";
import { AddQuestionDialog } from "./QuestionForm";

const STATUS = {
  not_started: "Not started",
  learning: "Learning",
  practising: "Practising",
  mastered: "Mastered",
} as const;

export function TopicPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const topics = useLearnTopics();
  const questions = useLearnQuestions(id);
  const update = useUpdateTopic();
  const removeTopic = useDeleteTopic();
  const [adding, setAdding] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (topics.isPending) return <Skeleton className="h-40" aria-busy="true" />;
  if (topics.isError) {
    return <ErrorState title="Could not load this topic" description={topics.error.message} onRetry={() => void topics.refetch()} />;
  }
  const topic = topics.data.find((t) => t.id === id);
  if (!topic) {
    return (
      <div className="flex flex-col gap-3">
        <ErrorState title="Topic not found" description="It may have been deleted or archived." />
        <Link href="/learn" className="text-sm text-accent-text underline">
          Back to Learn
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <Link href="/learn" className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="size-4" aria-hidden="true" /> All topics
      </Link>
      <PageHeader
        title={topic.title}
        description={topic.summary ?? topic.area ?? undefined}
        actions={
          <>
            <Select
              aria-label="Status"
              value={topic.status}
              onChange={(e) =>
                update.mutate({ id: topic.id, body: { status: e.target.value as keyof typeof STATUS } })
              }
              className="w-auto"
            >
              {Object.entries(STATUS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus aria-hidden="true" /> Add question
            </Button>
          </>
        }
      />

      <section aria-labelledby="questions-heading" className="flex flex-col gap-3">
        <h2 id="questions-heading" className="text-lg font-semibold tracking-tight">
          Questions{questions.data ? ` (${questions.data.total})` : ""}
        </h2>
        {questions.isPending && <Skeleton className="h-24" aria-busy="true" />}
        {questions.isError && (
          <ErrorState title="Could not load questions" description={questions.error.message} onRetry={() => void questions.refetch()} />
        )}
        {questions.isSuccess && questions.data.items.length === 0 && (
          <EmptyState
            title="No questions yet"
            description="Add questions you want to be able to answer from memory. Each one is scheduled for review once you answer it."
            action={
              <Button variant="primary" onClick={() => setAdding(true)}>
                <Plus aria-hidden="true" /> Add the first question
              </Button>
            }
          />
        )}
        {questions.isSuccess && questions.data.items.length > 0 && (
          <ul className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-surface">
            {questions.data.items.map((q) => (
              <QuestionRow key={q.id} question={q} />
            ))}
          </ul>
        )}
      </section>

      <section className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-danger/40 p-4">
        <div>
          <h2 className="font-medium">Delete this topic</h2>
          <p className="text-sm text-muted-foreground">
            Removes its {topic.question_count} questions and your history with them.
          </p>
        </div>
        <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
          <Trash2 aria-hidden="true" /> Delete topic
        </Button>
      </section>

      <AddQuestionDialog topicId={topic.id} open={adding} onOpenChange={setAdding} />
      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this topic?</DialogTitle>
            <DialogDescription>
              “{topic.title}” and its {topic.question_count} questions will be removed. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
            <Button
              variant="destructive"
              loading={removeTopic.isPending}
              onClick={() => removeTopic.mutate(topic.id, { onSuccess: () => router.replace("/learn") })}
            >
              Delete topic
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function QuestionRow({ question }: { question: LearnQuestion }) {
  const remove = useDeleteQuestion();
  return (
    <li className="flex items-start justify-between gap-3 p-3">
      <div className="min-w-0">
        <p className="font-medium">{question.stem}</p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <Badge tone="outline">{typeLabel(question.type)}</Badge>
          <Badge tone={question.status === "verified" ? "success" : "warning"}>
            {question.status === "verified" ? "Verified" : "Check this yourself"}
          </Badge>
          <Badge>Difficulty {question.difficulty}</Badge>
          {question.sources.length > 0 && <Badge tone="accent">{question.sources.length} source</Badge>}
        </div>
      </div>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`Delete question: ${question.stem}`}
        loading={remove.isPending}
        onClick={() => remove.mutate(question.id)}
      >
        <Trash2 aria-hidden="true" />
      </Button>
    </li>
  );
}

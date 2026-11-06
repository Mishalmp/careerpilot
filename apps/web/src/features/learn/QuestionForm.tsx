"use client";

import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { cn } from "@/lib/utils";

import { type LearnQuestionCreate, type LearnQuestionType, QUESTION_TYPES, useCreateQuestion } from "./hooks";

type OptionDraft = { text: string; is_correct: boolean };

const BLANK_OPTIONS: OptionDraft[] = [
  { text: "", is_correct: true },
  { text: "", is_correct: false },
  { text: "", is_correct: false },
];

/** Add a question to a topic. Multiple choice needs 3 to 5 options; the checks mirror the server's. */
export function AddQuestionDialog({
  topicId,
  open,
  onOpenChange,
}: {
  topicId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const create = useCreateQuestion();
  const [type, setType] = useState<LearnQuestionType>("mcq_single");
  const [stem, setStem] = useState("");
  const [explanation, setExplanation] = useState("");
  const [difficulty, setDifficulty] = useState("3");
  const [options, setOptions] = useState<OptionDraft[]>(BLANK_OPTIONS);
  const [rubric, setRubric] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceQuote, setSourceQuote] = useState("");

  const isChoice = type === "mcq_single" || type === "mcq_multi";

  function reset() {
    setType("mcq_single");
    setStem("");
    setExplanation("");
    setDifficulty("3");
    setOptions(BLANK_OPTIONS);
    setRubric("");
    setSourceUrl("");
    setSourceQuote("");
    create.reset();
  }

  function close(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  function setCorrect(index: number, checked: boolean) {
    setOptions((current) =>
      current.map((o, i) =>
        type === "mcq_single" ? { ...o, is_correct: i === index } : i === index ? { ...o, is_correct: checked } : o,
      ),
    );
  }

  function changeType(next: LearnQuestionType) {
    setType(next);
    if (next === "mcq_single") {
      // One correct option: keep only the first marked one.
      setOptions((current) => {
        const first = current.findIndex((o) => o.is_correct);
        return current.map((o, i) => ({ ...o, is_correct: i === Math.max(first, 0) }));
      });
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const body: LearnQuestionCreate = {
      topic_id: topicId,
      type,
      stem,
      tags: [],
      difficulty: Number(difficulty),
      explanation: explanation.trim() || undefined,
      options: isChoice ? options.map((o) => ({ text: o.text, is_correct: o.is_correct })) : [],
      rubric:
        !isChoice && rubric.trim()
          ? rubric
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
          : undefined,
      sources:
        sourceUrl.trim() && sourceQuote.trim()
          ? [{ url: sourceUrl.trim(), quote: sourceQuote.trim() }]
          : [],
    };
    create.mutate(body, { onSuccess: () => close(false) });
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] max-w-xl overflow-y-auto">
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>Add a question</DialogTitle>
            <DialogDescription>Write it so you can answer it from memory, without looking.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 sm:grid-cols-[1fr_8rem]">
            <Field label="Type">
              {(p) => (
                <Select value={type} onChange={(e) => changeType(e.target.value as LearnQuestionType)} {...p}>
                  {QUESTION_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Difficulty">
              {(p) => (
                <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} {...p}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>

          <Field label="Question" required>
            {(p) => <Textarea required rows={3} value={stem} onChange={(e) => setStem(e.target.value)} {...p} />}
          </Field>

          {isChoice ? (
            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 text-[0.8125rem] font-medium">
                Options{" "}
                <span className="font-normal text-muted-foreground">
                  ({type === "mcq_single" ? "mark the one correct option" : "mark every correct option"})
                </span>
              </legend>
              {options.map((option, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    type={type === "mcq_single" ? "radio" : "checkbox"}
                    name="correct"
                    aria-label={`Option ${index + 1} is correct`}
                    checked={option.is_correct}
                    onChange={(e) => setCorrect(index, e.target.checked)}
                    className="size-4 accent-[var(--primary)]"
                  />
                  <Input
                    aria-label={`Option ${index + 1}`}
                    placeholder={`Option ${index + 1}`}
                    value={option.text}
                    onChange={(e) =>
                      setOptions((current) => current.map((o, i) => (i === index ? { ...o, text: e.target.value } : o)))
                    }
                    className={cn(option.is_correct && "border-success")}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove option ${index + 1}`}
                    disabled={options.length <= 3}
                    onClick={() => setOptions((current) => current.filter((_, i) => i !== index))}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              ))}
              {options.length < 5 && (
                <div>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => setOptions((current) => [...current, { text: "", is_correct: false }])}
                  >
                    <Plus aria-hidden="true" /> Add option
                  </Button>
                </div>
              )}
            </fieldset>
          ) : (
            <Field label="Marking points" help="One per line. They are shown after you answer, so you can check yourself.">
              {(p) => <Textarea rows={3} value={rubric} onChange={(e) => setRubric(e.target.value)} {...p} />}
            </Field>
          )}

          <Field label="Explanation" help="Shown after answering.">
            {(p) => <Textarea rows={2} value={explanation} onChange={(e) => setExplanation(e.target.value)} {...p} />}
          </Field>

          <details className="rounded-md border border-border-subtle p-3 text-sm">
            <summary className="cursor-pointer font-medium">Source (optional)</summary>
            <div className="mt-3 flex flex-col gap-3">
              <Field label="Link">
                {(p) => <Input type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} {...p} />}
              </Field>
              <Field label="Short quote from the source" help="At most 300 characters.">
                {(p) => (
                  <Textarea rows={2} maxLength={300} value={sourceQuote} onChange={(e) => setSourceQuote(e.target.value)} {...p} />
                )}
              </Field>
            </div>
          </details>

          <p role="alert" className="min-h-5 text-sm text-danger-text">
            {create.error?.message}
          </p>
          <DialogFooter>
            <Button type="button" onClick={() => close(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={create.isPending}>
              Add question
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useState } from "react";

import { button, card, input, muted, primaryButton } from "@/components/ui";

import {
  type Story,
  type StoryDraft,
  useDeleteStory,
  useSaveStory,
  useStories,
} from "./hooks";

const PARTS = [
  ["situation", "Situation: what was happening?"],
  ["task", "Task: what was your part?"],
  ["action", "Action: what did you do?"],
  ["result", "Result: what changed? Use only numbers you can back up."],
] as const;

const empty: StoryDraft = {
  title: "",
  situation: "",
  task: "",
  action: "",
  result: "",
  tags: [],
  evidence: null,
};

function Editor({ story, onDone }: { story?: Story; onDone: () => void }) {
  const save = useSaveStory();
  const [draft, setDraft] = useState<StoryDraft>(
    story ? { ...story, tags: story.tags ?? [] } : empty,
  );
  const [tags, setTags] = useState((story?.tags ?? []).join(", "));

  return (
    <form
      className={`${card} space-y-2`}
      onSubmit={(e) => {
        e.preventDefault();
        const list = tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
        save.mutate(
          {
            id: story?.id,
            body: {
              ...draft,
              tags: list,
              evidence: draft.evidence?.trim() || null,
            },
          },
          { onSuccess: onDone },
        );
      }}
    >
      <input
        className={input}
        required
        placeholder="A short name for this story"
        aria-label="Title"
        value={draft.title}
        onChange={(e) => setDraft({ ...draft, title: e.target.value })}
      />
      {PARTS.map(([key, label]) => (
        <label key={key} className="block space-y-1 text-sm">
          <span>{label}</span>
          <textarea
            className={`${input} min-h-20`}
            required
            value={draft[key]}
            onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
          />
        </label>
      ))}
      <input
        className={input}
        placeholder="Themes, comma separated (ownership, conflict, failure...)"
        aria-label="Themes"
        value={tags}
        onChange={(e) => setTags(e.target.value)}
      />
      <input
        className={input}
        placeholder="Where this is written down (a note, a commit, a document)"
        aria-label="Evidence"
        value={draft.evidence ?? ""}
        onChange={(e) => setDraft({ ...draft, evidence: e.target.value })}
      />
      <div className="flex gap-2">
        <button
          type="submit"
          className={primaryButton}
          disabled={save.isPending}
        >
          Save story
        </button>
        <button type="button" className={button} onClick={onDone}>
          Cancel
        </button>
      </div>
      {save.error && (
        <p role="alert" className="text-sm text-danger-text">
          {save.error.message}
        </p>
      )}
    </form>
  );
}

function StoryCard({ story }: { story: Story }) {
  const [editing, setEditing] = useState(false);
  const remove = useDeleteStory();
  if (editing) return <Editor story={story} onDone={() => setEditing(false)} />;
  return (
    <li className={`${card} space-y-2`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold">{story.title}</h3>
        <span className="flex flex-wrap gap-1">
          {story.tags?.map((t) => (
            <span
              key={t}
              className="rounded bg-surface-hover px-1.5 text-xs"
            >
              {t}
            </span>
          ))}
        </span>
      </div>
      <dl className="space-y-1 text-sm">
        {PARTS.map(([key]) => (
          <div key={key}>
            <dt className="inline font-medium capitalize">{key}: </dt>
            <dd className="inline">{story[key]}</dd>
          </div>
        ))}
      </dl>
      {story.evidence && <p className={muted}>Source: {story.evidence}</p>}
      {story.hints.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-warning-text">
          {story.hints.map((h) => (
            <li key={h}>{h}</li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          className={button}
          onClick={() => setEditing(true)}
        >
          Edit
        </button>
        <button
          type="button"
          className={button}
          disabled={remove.isPending}
          onClick={() => {
            if (window.confirm(`Delete "${story.title}"?`))
              remove.mutate(story.id);
          }}
        >
          Delete
        </button>
      </div>
    </li>
  );
}

export function StoriesPage() {
  const [tag, setTag] = useState("");
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const stories = useStories(tag, q);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Story bank</h1>
      <p className={muted}>
        Behavioural questions (&ldquo;tell me about a time...&rdquo;) are
        answered from stories you have prepared. Keep each one true and
        traceable to something you can point to.
      </p>
      <div className="flex flex-wrap gap-2">
        <input
          className={`${input} w-48`}
          placeholder="Filter by theme"
          aria-label="Filter by theme"
          value={tag}
          onChange={(e) => setTag(e.target.value)}
        />
        <input
          className={`${input} w-48`}
          placeholder="Search text"
          aria-label="Search text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button
          type="button"
          className={primaryButton}
          onClick={() => setAdding(true)}
        >
          New story
        </button>
      </div>
      {adding && <Editor onDone={() => setAdding(false)} />}
      {stories.isPending && <p className={muted}>Loading...</p>}
      {stories.isError && (
        <p role="alert">Could not load stories: {stories.error.message}</p>
      )}
      {stories.data?.length === 0 && <p className={muted}>No stories yet.</p>}
      <ul className="space-y-3">
        {stories.data?.map((s) => (
          <StoryCard key={`${s.id}-${s.updated_at}`} story={s} />
        ))}
      </ul>
    </div>
  );
}

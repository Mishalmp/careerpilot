"use client";

import Link from "next/link";
import { useState } from "react";

import { Modal } from "@/components/Modal";
import { button, card, input, muted, primaryButton, select } from "@/components/ui";
import type { StudyKind, Topic, TopicStatus } from "@/lib/api/types";

import { useLogSession, useTopics, useUpdateTopic } from "./hooks";
import { useProblems } from "@/features/practice/hooks";

import { PrepNav } from "./PrepNav";
import { todayLocal } from "@/lib/dates";

const STATUSES: TopicStatus[] = ["Not started", "Learning", "Revised", "Mock-tested"];
const KINDS: StudyKind[] = ["learn", "practice", "review", "mock"];
const PRIORITY_TONE = {
  High: "text-red-700 dark:text-red-300",
  Medium: "text-amber-700 dark:text-amber-300",
  Low: "text-zinc-500",
} as const;

export function TopicsPage() {
  const [area, setArea] = useState("");
  const [status, setStatus] = useState<TopicStatus | "">("");
  const [logging, setLogging] = useState<Topic | null>(null);
  const all = useTopics({});
  const topics = useTopics({ area: area || undefined, status: status || undefined });
  const update = useUpdateTopic();
  const problems = useProblems();
  const practiceCount = new Map<string, number>();
  for (const problem of problems.data ?? []) {
    for (const key of problem.topic_keys) practiceCount.set(key, (practiceCount.get(key) ?? 0) + 1);
  }

  const areas = [...new Set((all.data ?? []).map((t) => t.area))];
  const grouped = new Map<string, Topic[]>();
  for (const topic of topics.data ?? []) {
    grouped.set(topic.area, [...(grouped.get(topic.area) ?? []), topic]);
  }
  const today = todayLocal();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Prep</h1>
      <PrepNav />

      <div className="flex flex-wrap gap-3">
        <select aria-label="Filter by area" value={area} onChange={(e) => setArea(e.target.value)} className={select}>
          <option value="">All areas</option>
          {areas.map((a) => <option key={a}>{a}</option>)}
        </select>
        <select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => setStatus(e.target.value as TopicStatus | "")}
          className={select}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>

      {topics.isPending && <p className={muted}>Loading...</p>}
      {topics.isSuccess && topics.data.length === 0 && (
        <p className={muted}>
          {all.data?.length === 0
            ? "No topics yet. Load the curriculum from the Roadmap tab."
            : "No topics match these filters."}
        </p>
      )}

      {[...grouped.entries()].map(([areaName, items]) => (
        <section key={areaName} className={card}>
          <h2 className="mb-2 font-semibold">{areaName}</h2>
          <ul className="divide-y divide-black/5 dark:divide-white/10">
            {items.map((topic) => (
              <li key={topic.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <span className="min-w-60 flex-1">
                  {topic.title}
                  <span className={`ml-2 text-xs ${PRIORITY_TONE[topic.priority]}`}>{topic.priority}</span>
                  {topic.next_review_on && (
                    <span className={`ml-2 text-xs ${topic.next_review_on <= today ? "font-medium text-red-600 dark:text-red-400" : "text-zinc-500"}`}>
                      review {topic.next_review_on <= today ? "due" : topic.next_review_on}
                    </span>
                  )}
                </span>
                <select
                  aria-label={`Confidence for ${topic.title}`}
                  value={topic.confidence ?? ""}
                  onChange={(e) =>
                    update.mutate({ id: topic.id, confidence: e.target.value ? Number(e.target.value) : null })
                  }
                  className={select}
                >
                  <option value="">Confidence</option>
                  {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} of 5</option>)}
                </select>
                <select
                  aria-label={`Status for ${topic.title}`}
                  value={topic.status}
                  onChange={(e) => update.mutate({ id: topic.id, status: e.target.value as TopicStatus })}
                  className={select}
                >
                  {STATUSES.map((s) => <option key={s}>{s}</option>)}
                </select>
                {practiceCount.has(topic.key) && (
                  <Link href={`/practice?topic=${encodeURIComponent(topic.key)}`} className={button}>
                    Practise ({practiceCount.get(topic.key)})
                  </Link>
                )}
                <button type="button" onClick={() => setLogging(topic)} className={button}>
                  Log session
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <LogSessionDialog topic={logging} onClose={() => setLogging(null)} />
    </div>
  );
}

function LogSessionDialog({ topic, onClose }: { topic: Topic | null; onClose: () => void }) {
  const log = useLogSession();
  const [minutes, setMinutes] = useState("30");
  const [kind, setKind] = useState<StudyKind>("learn");
  const [notes, setNotes] = useState("");

  return (
    <Modal open={topic !== null} onClose={onClose} title={topic ? `Log a session: ${topic.title}` : ""}>
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (!topic) return;
          log.mutate(
            { topicId: topic.id, minutes: Number(minutes), kind, notes: notes.trim() || undefined },
            { onSuccess: () => { setNotes(""); onClose(); } },
          );
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-sm">
            <span>Minutes</span>
            <input type="number" required min={1} max={720} value={minutes} onChange={(e) => setMinutes(e.target.value)} className={input} />
          </label>
          <label className="space-y-1 text-sm">
            <span>Kind</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as StudyKind)} className={input}>
              {KINDS.map((k) => <option key={k}>{k}</option>)}
            </select>
          </label>
        </div>
        <label className="block space-y-1 text-sm">
          <span>Notes</span>
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className={input} />
        </label>
        <p role="alert" className="min-h-5 text-sm text-red-600 dark:text-red-400">{log.error?.message}</p>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={button}>Cancel</button>
          <button type="submit" disabled={log.isPending} className={primaryButton}>Save session</button>
        </div>
      </form>
    </Modal>
  );
}

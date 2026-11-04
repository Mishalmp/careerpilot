"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useDeferredValue, useState } from "react";

import { button, input, muted, select } from "@/components/ui";

import { type ProblemFilters, useProblems } from "./hooks";

const TONE = {
  Easy: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200",
  Medium: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
  Hard: "bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200",
} as const;

export function DifficultyBadge({ difficulty }: { difficulty: keyof typeof TONE }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TONE[difficulty]}`}>
      {difficulty}
    </span>
  );
}

const PROGRESS_LABEL = { solved: "Solved", attempted: "Attempted", unsolved: "" } as const;

export function ProblemsPage() {
  const params = useSearchParams();
  const router = useRouter();
  const topic = params.get("topic") ?? undefined;
  const [search, setSearch] = useState("");
  const [difficulty, setDifficulty] = useState<ProblemFilters["difficulty"] | "">("");
  const [kind, setKind] = useState<ProblemFilters["kind"] | "">("");
  const [progress, setProgress] = useState<ProblemFilters["progress"] | "">("");
  const q = useDeferredValue(search.trim());

  const problems = useProblems({
    q: q || undefined,
    difficulty: difficulty || undefined,
    kind: kind || undefined,
    progress: progress || undefined,
    topic,
  });
  const all = useProblems();
  const solved = all.data?.filter((p) => p.status === "solved").length ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Practice</h1>
        {all.data && (
          <span className={muted}>
            {solved} of {all.data.length} solved
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          aria-label="Search problems"
          placeholder="Search problems"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={`${input} max-w-60`}
        />
        <select aria-label="Difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value as typeof difficulty)} className={select}>
          <option value="">Any difficulty</option>
          <option>Easy</option>
          <option>Medium</option>
          <option>Hard</option>
        </select>
        <select aria-label="Type" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} className={select}>
          <option value="">Code and SQL</option>
          <option value="function">Code (Python, JS, TS)</option>
          <option value="sql">SQL</option>
        </select>
        <select aria-label="Progress" value={progress} onChange={(e) => setProgress(e.target.value as typeof progress)} className={select}>
          <option value="">Any progress</option>
          <option value="unsolved">Not started</option>
          <option value="attempted">Attempted</option>
          <option value="solved">Solved</option>
        </select>
        {topic && (
          <button type="button" className={button} onClick={() => router.replace("/practice")}>
            Clear topic filter &times;
          </button>
        )}
      </div>

      {problems.isPending && <p className={muted}>Loading...</p>}
      {problems.isError && <p role="alert" className="text-red-600">Could not load problems.</p>}
      {problems.data?.length === 0 && <p className={muted}>No problems match these filters.</p>}

      {problems.data && problems.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <caption className="sr-only">Practice problems</caption>
            <thead className="border-b border-black/10 text-xs uppercase text-zinc-500 dark:border-white/15">
              <tr>
                <th scope="col" className="py-2 pr-3">Problem</th>
                <th scope="col" className="py-2 pr-3">Level</th>
                <th scope="col" className="py-2 pr-3">Topics</th>
                <th scope="col" className="py-2 pr-3">Languages</th>
                <th scope="col" className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {problems.data.map((problem) => (
                <tr key={problem.slug} className="border-b border-black/5 dark:border-white/10">
                  <td className="py-2 pr-3">
                    <Link href={`/practice/${problem.slug}`} className="font-medium hover:underline">
                      {problem.title}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">
                    <DifficultyBadge difficulty={problem.difficulty} />
                  </td>
                  <td className={`${muted} py-2 pr-3`}>{problem.tags.join(", ")}</td>
                  <td className={`${muted} py-2 pr-3`}>{problem.languages.join(", ")}</td>
                  <td className="py-2">
                    <span
                      className={
                        problem.status === "solved"
                          ? "font-medium text-emerald-700 dark:text-emerald-300"
                          : muted
                      }
                    >
                      {PROGRESS_LABEL[problem.status]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

"use client";

import { Building2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { IconChip } from "@/components/ui/stat";
import { cn } from "@/lib/utils";

import { useFollowSuggested, useSuggestedBoards } from "./hooks";

const FILTERS = [
  { key: "india", label: "Hiring in India" },
  { key: "remote", label: "Remote roles" },
  { key: "all", label: "All" },
] as const;

/**
 * Company boards that were checked and work (content/job-boards.yaml). Following one means its jobs
 * are read once a day and the ones that fit your searches and CV reach your list on their own.
 */
export function SuggestedBoards() {
  const boards = useSuggestedBoards();
  const follow = useFollowSuggested();
  const [filter, setFilter] =
    useState<(typeof FILTERS)[number]["key"]>("india");
  const all = boards.data ?? [];
  if (boards.isSuccess && all.length === 0) return null;
  const shown = all.filter((b) => filter === "all" || b.tags.includes(filter));
  const todo = shown.filter((b) => !b.followed);

  return (
    <Card>
      <CardHeader className="flex-row items-start gap-3">
        <IconChip icon={Building2} tone="accent" />
        <div className="min-w-0">
          <CardTitle>Companies worth following</CardTitle>
          <CardDescription className="mt-1">
            Real company career boards, each checked to work. Their jobs are
            read once a day; only the ones that fit your searches and your CV
            reach your list. Counts are a snapshot of open roles.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Show" className="flex gap-1">
            {FILTERS.map((f) => (
              <Button
                key={f.key}
                size="sm"
                variant={filter === f.key ? "secondary" : "ghost"}
                aria-pressed={filter === f.key}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </Button>
            ))}
          </div>
          <Button
            size="sm"
            variant="primary"
            className={cn("ml-auto")}
            disabled={todo.length === 0 || follow.isPending}
            onClick={() => follow.mutate(todo.map((b) => b.key))}
          >
            {todo.length === 0
              ? "All followed"
              : `Follow all ${todo.length} shown`}
          </Button>
        </div>
        <ul
          className="grid gap-2 sm:grid-cols-2"
          aria-label="Suggested company boards"
        >
          {shown.map((b) => (
            <li
              key={b.key}
              className="flex items-center justify-between gap-3 rounded-lg border border-border-subtle p-3"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{b.company}</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <Badge tone="neutral">{b.roles} roles</Badge>
                  {b.india > 0 && (
                    <Badge tone="accent">{b.india} in India</Badge>
                  )}
                  {b.remote > 0 && (
                    <Badge tone="success">{b.remote} remote</Badge>
                  )}
                </div>
              </div>
              <Button
                size="sm"
                variant={b.followed ? "ghost" : "secondary"}
                disabled={b.followed || follow.isPending}
                onClick={() => follow.mutate([b.key])}
                aria-label={
                  b.followed
                    ? `${b.company} is followed`
                    : `Follow ${b.company}`
                }
              >
                {b.followed ? "Followed" : "Follow"}
              </Button>
            </li>
          ))}
        </ul>
        {follow.error && (
          <p role="alert" className="text-sm text-danger-text">
            {follow.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

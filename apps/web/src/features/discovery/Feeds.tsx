"use client";

import { Rss } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { IconChip } from "@/components/ui/stat";

import { type DiscoverySource, useAddSource } from "./hooks";

const FEEDS = [
  { kind: "remoteok", label: "Remote OK", about: "Remote jobs worldwide." },
  {
    kind: "remotive",
    label: "Remotive",
    about: "Remote jobs, shown a day late by their rules.",
  },
  {
    kind: "weworkremotely",
    label: "We Work Remotely",
    about: "Remote programming jobs.",
  },
  {
    kind: "himalayas",
    label: "Himalayas",
    about: "Remote jobs, with the countries each one allows.",
  },
  {
    kind: "arbeitnow",
    label: "Arbeitnow",
    about: "Jobs in Germany and Europe, on site and remote.",
  },
] as const;

/**
 * Free public job feeds that list many companies, so you are not limited to the boards of companies
 * you already know. Each is read once a day and only keeps what fits your searches.
 */
export function Feeds({ followed }: { followed: DiscoverySource[] }) {
  const add = useAddSource();
  const have = new Set(followed.map((s) => s.kind));
  return (
    <Card>
      <CardHeader className="flex-row items-start gap-3">
        <IconChip icon={Rss} tone="success" />
        <div className="min-w-0">
          <CardTitle>Free job feeds</CardTitle>
          <CardDescription className="mt-1">
            Public feeds with jobs from many companies. Each job links back to
            where it was listed. LinkedIn, Indeed, Glassdoor and Naukri are not
            read here (their terms forbid it); when you find a job there, add it
            from the Jobs page with its link and CareerPilot researches it.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="grid gap-2 sm:grid-cols-2">
          {FEEDS.map((f) => (
            <li
              key={f.kind}
              className="flex items-center justify-between gap-3 rounded-lg border border-border-subtle p-3"
            >
              <div className="min-w-0">
                <p className="font-medium">{f.label}</p>
                <p className="text-xs text-muted-foreground">{f.about}</p>
              </div>
              <Button
                size="sm"
                variant={have.has(f.kind) ? "ghost" : "secondary"}
                disabled={have.has(f.kind) || add.isPending}
                onClick={() =>
                  add.mutate({
                    kind: f.kind,
                    board: "all",
                    company_name: f.label,
                    include: [],
                    exclude: [],
                  })
                }
                aria-label={
                  have.has(f.kind)
                    ? `${f.label} is followed`
                    : `Follow ${f.label}`
                }
              >
                {have.has(f.kind) ? "Followed" : "Follow"}
              </Button>
            </li>
          ))}
        </ul>
        {add.error && (
          <p role="alert" className="mt-2 text-sm text-danger-text">
            {add.error.message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

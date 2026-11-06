"use client";

import { Briefcase, Plus, Search, Trash2 } from "lucide-react";
import { useState } from "react";

import { Logo, LogoMark } from "@/components/Logo";
import { ThemeMenu } from "@/components/ThemeMenu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, EmptyState, ErrorState } from "@/components/ui/states";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      {children}
    </section>
  );
}

const SWATCHES = [
  ["background", "bg-background"],
  ["surface", "bg-surface"],
  ["surface-muted", "bg-surface-muted"],
  ["surface-hover", "bg-surface-hover"],
  ["primary", "bg-primary"],
  ["accent-soft", "bg-accent-soft"],
  ["success", "bg-success"],
  ["warning", "bg-warning"],
  ["danger", "bg-danger"],
  ["border", "bg-border"],
] as const;

export function Gallery() {
  const [on, setOn] = useState(true);
  const [loading, setLoading] = useState(false);
  return (
    <TooltipProvider>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 p-6">
        <header className="flex items-center justify-between">
          <div>
            <Logo />
            <p className="mt-1 text-sm text-muted-foreground">Design system gallery (development only)</p>
          </div>
          <ThemeMenu />
        </header>

        <Section title="Logo">
          <div className="flex flex-wrap items-center gap-6">
            <Logo />
            <Logo variant="compact" />
            <LogoMark className="size-5" />
            <LogoMark className="size-12" />
          </div>
        </Section>

        <Section title="Colour tokens">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            {SWATCHES.map(([name, cls]) => (
              <div key={name} className="flex flex-col gap-1">
                <div className={`h-12 rounded-md border border-border-subtle ${cls}`} />
                <span className="text-xs text-muted-foreground">{name}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Typography">
          <div className="flex flex-col gap-1">
            <p className="text-2xl font-semibold tracking-tight">Page title 24</p>
            <p className="text-xl font-semibold">Section title 20</p>
            <p className="text-base">Lead 16: the quick brown fox jumps over the lazy dog</p>
            <p>Body 14: the quick brown fox jumps over the lazy dog</p>
            <p className="text-[0.8125rem] text-muted-foreground">Secondary 13: supporting text and help</p>
            <p className="font-mono text-sm">Mono: SELECT * FROM jobs WHERE owner_id = 1;</p>
            <p className="tabular">Tabular: 1,234.50 · 0,987.25</p>
          </div>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary"><Plus aria-hidden="true" /> Add job</Button>
            <Button>Secondary</Button>
            <Button variant="soft">Soft</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive"><Trash2 aria-hidden="true" /> Delete</Button>
            <Button variant="link">Link</Button>
            <Button variant="primary" size="sm">Small</Button>
            <Button variant="primary" size="lg">Large</Button>
            <Button variant="primary" disabled>Disabled</Button>
            <Button
              variant="primary"
              loading={loading}
              onClick={() => {
                setLoading(true);
                setTimeout(() => setLoading(false), 1500);
              }}
            >
              {loading ? "Saving" : "Click to load"}
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Search"><Search aria-hidden="true" /></Button>
              </TooltipTrigger>
              <TooltipContent>Search</TooltipContent>
            </Tooltip>
          </div>
        </Section>

        <Section title="Badges">
          <div className="flex flex-wrap gap-2">
            <Badge>Neutral</Badge>
            <Badge tone="accent">Applied</Badge>
            <Badge tone="success">Offer</Badge>
            <Badge tone="warning">Needs check</Badge>
            <Badge tone="danger">Rejected</Badge>
            <Badge tone="outline">Draft</Badge>
          </div>
        </Section>

        <Section title="Form controls">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Company" help="As written on the job post.">
              {(p) => <Input placeholder="Acme Inc." {...p} />}
            </Field>
            <Field label="Link" error="Enter a link that starts with http:// or https://">
              {(p) => <Input defaultValue="acme.com" {...p} />}
            </Field>
            <Field label="Status">
              {(p) => (
                <Select defaultValue="applied" {...p}>
                  <option value="saved">Saved</option>
                  <option value="applied">Applied</option>
                  <option value="interview">Interview</option>
                </Select>
              )}
            </Field>
            <Field label="Notes">{(p) => <Textarea placeholder="Anything worth remembering" {...p} />}</Field>
            <div className="flex items-center gap-3">
              <Switch checked={on} onCheckedChange={setOn} aria-label="Daily digest" />
              <span className="text-sm">Daily digest {on ? "on" : "off"}</span>
            </div>
          </div>
        </Section>

        <Section title="Cards and tabs">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Applications this week</CardTitle>
                <CardDescription>Sent, replied and interviews</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-semibold tabular">12</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent>
                <Tabs defaultValue="overview">
                  <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="timeline">Timeline</TabsTrigger>
                    <TabsTrigger value="notes">Notes</TabsTrigger>
                  </TabsList>
                  <TabsContent value="overview">Overview content</TabsContent>
                  <TabsContent value="timeline">Timeline content</TabsContent>
                  <TabsContent value="notes">Notes content</TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </Section>

        <Section title="Dialog">
          <div>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="secondary">Open dialog</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Delete this job?</DialogTitle>
                  <DialogDescription>
                    The job and its 4 timeline events move to Trash for 30 days. You can restore it from there.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button>Cancel</Button>
                  <Button variant="destructive">Delete job</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </Section>

        <Section title="Loading, empty, error, notices">
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardContent className="flex flex-col gap-3">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-5/6" />
              </CardContent>
            </Card>
            <EmptyState
              icon={<Briefcase aria-hidden="true" />}
              title="No jobs yet"
              description="Paste a job link or description and CareerPilot will track it for you."
              action={<Button variant="primary"><Plus aria-hidden="true" /> Add your first job</Button>}
            />
            <ErrorState description="The server did not answer. Your data is safe." onRetry={() => undefined} />
            <div className="flex flex-col gap-3">
              <Alert tone="info" title="Heads up">Research runs use your daily AI budget.</Alert>
              <Alert tone="success">Saved.</Alert>
              <Alert tone="warning" title="Unverified">This question has no checked source yet.</Alert>
              <Alert tone="danger" title="Could not save">The job changed in another tab. Reload to see it.</Alert>
            </div>
          </div>
        </Section>
      </div>
    </TooltipProvider>
  );
}

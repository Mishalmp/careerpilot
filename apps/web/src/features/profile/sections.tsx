"use client";

import { Briefcase, FileText, GitBranch, Link2, Sparkles, Target, Trash2, Upload, UserRound } from "lucide-react";
import { useRef, useState } from "react";

import { Alert } from "@/components/ui/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import { IconChip, type Tone } from "@/components/ui/stat";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

import { TagInput, ToggleChips } from "./Chips";
import { type Draft, LEVELS, LINK_KINDS, REGIONS, WORK_MODES } from "./draft";
import {
  type Profile,
  useAnalyseCv,
  useForgetCv,
  useReadGithub,
  useUpdateProfile,
  useUploadCv,
} from "./hooks";

type Edit = (patch: Partial<Draft>) => void;

export function Section({
  icon,
  tone = "accent",
  title,
  description,
  children,
  className,
}: {
  icon: LucideIcon;
  tone?: Tone;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex-row items-start gap-3">
        <IconChip icon={icon} tone={tone} />
        <div className="min-w-0">
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription className="mt-1">{description}</CardDescription> : null}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  );
}

export function AboutSection({ draft, edit }: { draft: Draft; edit: Edit }) {
  return (
    <Section icon={UserRound} title="About you" description="Who you are now. The app uses this to talk to you, and to write in your voice later.">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name" required>
          {(p) => <Input autoComplete="name" value={draft.full_name} onChange={(e) => edit({ full_name: e.target.value })} {...p} />}
        </Field>
        <Field label="Current role" required help="What you do today, or “Student” or “Between jobs”.">
          {(p) => <Input placeholder="e.g. Backend Developer" value={draft.current_role} onChange={(e) => edit({ current_role: e.target.value })} {...p} />}
        </Field>
        <Field label="Where you live">
          {(p) => <Input placeholder="e.g. Pune, India" value={draft.location} onChange={(e) => edit({ location: e.target.value })} {...p} />}
        </Field>
        <Field label="Years of experience">
          {(p) => <Input type="number" min={0} max={60} value={draft.years} onChange={(e) => edit({ years: e.target.value })} {...p} />}
        </Field>
        <Field label="Contact email" help="The address employers should write to. Kept here for you; nothing is sent from it.">
          {(p) => <Input type="email" autoComplete="email" placeholder="you@example.com" value={draft.contact_email} onChange={(e) => edit({ contact_email: e.target.value })} {...p} />}
        </Field>
        <Field label="Phone number" help="With the country code, for example +91 98765 43210.">
          {(p) => <Input type="tel" autoComplete="tel" placeholder="+91 98765 43210" value={draft.phone} onChange={(e) => edit({ phone: e.target.value })} {...p} />}
        </Field>
        <Field label="One line about you" help="Optional, for example “Backend engineer who likes data pipelines”." className="sm:col-span-2">
          {(p) => <Input value={draft.headline} onChange={(e) => edit({ headline: e.target.value })} {...p} />}
        </Field>
      </div>
    </Section>
  );
}

export function GoalsSection({ draft, edit, suggestions }: { draft: Draft; edit: Edit; suggestions: string[] }) {
  return (
    <Section icon={Target} tone="violet" title="What you are looking for" description="The roles and conditions you want. Scoring, research and the daily list all aim at this, not at a fixed role.">
      <TagInput
        label="Roles you want"
        items={draft.target_roles}
        onChange={(next) => edit({ target_roles: next })}
        placeholder="e.g. Python Developer"
        suggestions={suggestions}
        emptyText="Add at least one role."
      />
      <ToggleChips label="Level" options={LEVELS} value={draft.target_levels} onChange={(next) => edit({ target_levels: next })} />
      <ToggleChips label="Where" options={REGIONS} value={draft.regions} onChange={(next) => edit({ regions: next })} />
      <ToggleChips label="Work mode" options={WORK_MODES} value={draft.work_modes} onChange={(next) => edit({ work_modes: next })} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Lowest pay (LPA)" help="The least you would accept, in lakhs per year. Optional.">
          {(p) => <Input type="number" min={0} step="0.5" value={draft.salary_floor} onChange={(e) => edit({ salary_floor: e.target.value })} {...p} />}
        </Field>
        <Field label="Target pay (LPA)" help="What you are aiming for. Optional.">
          {(p) => <Input type="number" min={0} step="0.5" value={draft.salary_target} onChange={(e) => edit({ salary_target: e.target.value })} {...p} />}
        </Field>
      </div>
      <label className="flex items-center gap-3 text-sm">
        <Switch checked={draft.needs_visa} onCheckedChange={(on) => edit({ needs_visa: on })} aria-label="I need visa sponsorship" />
        I need visa sponsorship for jobs abroad
      </label>
    </Section>
  );
}

/** Upload a file (PDF, Word, text or a picture) or paste text. The file itself is never kept. */
export function CvSection({ profile }: { profile: Profile }) {
  const upload = useUploadCv();
  const analyse = useAnalyseCv();
  const forget = useForgetCv();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [text, setText] = useState("");
  const error = upload.error ?? analyse.error ?? forget.error;
  const cv = profile.cv;
  const pick = (file: File | undefined) => file && upload.mutate(file);
  return (
    <Section icon={FileText} tone="success" title="Your CV" description="Upload it or paste it. It is read by rules on this computer: nothing is sent to a search service or a model, and an uploaded file is not kept.">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          pick(e.dataTransfer.files[0]);
        }}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-6 text-center transition-colors",
          over ? "border-primary bg-accent-soft" : "border-border hover:border-primary/60 hover:bg-surface-muted",
        )}
      >
        <Upload className="size-6 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm">
          Drop your CV here, or{" "}
          <Button type="button" variant="link" onClick={() => input.current?.click()} loading={upload.isPending}>
            choose a file
          </Button>
        </p>
        <p className="text-xs text-muted-foreground">PDF, Word (.docx), text or a picture, up to 5 MB. Scans need OCR.</p>
        <input
          ref={input}
          type="file"
          className="sr-only"
          aria-label="CV file"
          accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,application/pdf,text/plain,image/png,image/jpeg"
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
      {upload.data?.notes.map((n) => (
        <Alert key={n} tone="info">
          {n}
        </Alert>
      ))}
      {cv.has_cv && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-success-soft px-3 py-2 text-sm text-success-text">
          <span>
            CV read{cv.filename ? `: ${cv.filename}` : ""} ({cv.source}, {cv.chars?.toLocaleString()} characters).
          </span>
          <Button size="sm" variant="ghost" onClick={() => forget.mutate()} loading={forget.isPending}>
            <Trash2 aria-hidden="true" /> Forget the text
          </Button>
        </div>
      )}
      <details className="text-sm">
        <summary className="cursor-pointer font-medium">Or paste the text</summary>
        <form
          className="mt-3 flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            analyse.mutate(text, { onSuccess: () => setText("") });
          }}
        >
          <Field label="CV text" help={cv.has_cv ? "A CV is stored. Paste a new one to replace what was read from it." : "Plain text works best."}>
            {(p) => <Textarea rows={7} value={text} onChange={(e) => setText(e.target.value)} {...p} />}
          </Field>
          <div>
            <Button type="submit" variant="primary" loading={analyse.isPending} disabled={text.trim().length < 20}>
              <FileText aria-hidden="true" /> Read my CV
            </Button>
          </div>
        </form>
      </details>
      {error && (
        <p role="alert" className="text-sm text-danger-text">
          {error.message}
        </p>
      )}
    </Section>
  );
}

/** What was read from the CV (and added by hand). Each change is saved at once. */
export function ReadSection({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  return (
    <Section icon={Sparkles} tone="warning" title="Skills and role titles" description="Read from your CV. Wrong or missing? Change them: changes save as you make them.">
      <TagInput label="Role titles" items={profile.role_titles} placeholder="e.g. Backend Developer" busy={update.isPending} onChange={(next) => update.mutate({ role_titles: next })} emptyText="None yet. Read a CV or add some." />
      <TagInput label="Skills" items={profile.skills} placeholder="e.g. postgresql" busy={update.isPending} onChange={(next) => update.mutate({ skills: next })} emptyText="None yet. Read a CV or add some." />
      {update.error && (
        <p role="alert" className="text-sm text-danger-text">
          {update.error.message}
        </p>
      )}
    </Section>
  );
}

export function LinksSection({ draft, edit, profile }: { draft: Draft; edit: Edit; profile: Profile }) {
  const github = useReadGithub();
  const update = useUpdateProfile();
  const hasGithubSaved = profile.links.some((l) => l.kind === "github");
  return (
    <Section icon={Link2} tone="violet" title="Public profiles" description="All optional. They are links you keep here; only GitHub (public repositories) can be read, and only when you ask.">
      <div className="grid gap-4 sm:grid-cols-2">
        {LINK_KINDS.map((k) => (
          <Field key={k.kind} label={k.label} help={k.note}>
            {(p) => (
              <Input
                type="url"
                inputMode="url"
                placeholder={k.placeholder}
                value={draft.links[k.kind]}
                onChange={(e) => edit({ links: { ...draft.links, [k.kind]: e.target.value } })}
                {...p}
              />
            )}
          </Field>
        ))}
      </div>
      <div className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface-muted p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={() => github.mutate()} loading={github.isPending} disabled={!hasGithubSaved}>
            <GitBranch aria-hidden="true" /> Read my GitHub
          </Button>
          <span className="text-xs text-muted-foreground">
            {hasGithubSaved ? "Looks at the languages of your own public repositories (60 reads an hour allowed)." : "Save a GitHub link first."}
          </span>
        </div>
        {github.error && (
          <p role="alert" className="text-sm text-danger-text">
            {github.error.message}
          </p>
        )}
        {github.data && (
          <div className="flex flex-col gap-2 text-sm">
            <p>
              Read {github.data.repos_read} repositories of <strong>{github.data.username}</strong>:{" "}
              {github.data.languages.map((l) => `${l.name} (${l.repos})`).join(", ") || "no languages"}.
            </p>
            {github.data.notes.map((n) => (
              <p key={n} className="text-muted-foreground">
                {n}
              </p>
            ))}
            {github.data.suggested_skills.length > 0 ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted-foreground">Add to your skills:</span>
                {github.data.suggested_skills.map((s) => (
                  <button
                    key={s}
                    type="button"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ skills: [...profile.skills, s] }, { onSuccess: () => github.reset() })}
                    className="rounded-full border border-dashed border-border px-2 py-0.5 text-[0.8125rem] transition-colors hover:border-primary hover:bg-accent-soft hover:text-accent-text"
                  >
                    + {s}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground">Nothing new to add.</p>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}

export function ReviewSection({ profile }: { profile: Profile }) {
  const rows: [string, string][] = [
    ["Name", profile.full_name ?? "-"],
    ["Current role", profile.current_role ?? "-"],
    ["Looking for", profile.target_roles.join(", ") || "-"],
    ["Contact", [profile.contact_email, profile.phone].filter(Boolean).join(" · ") || "-"],
    ["Where and how", [...profile.regions, ...profile.work_modes].join(", ") || "-"],
    ["CV", profile.cv.has_cv ? `${profile.cv.source}${profile.cv.filename ? `: ${profile.cv.filename}` : ""}` : "not added"],
    ["Skills", profile.skills.length ? `${profile.skills.length} found` : "none yet"],
    ["Links", profile.links.map((l) => l.kind).join(", ") || "none"],
  ];
  return (
    <Section icon={Briefcase} tone="success" title="Review" description="This is what the app will use. You can change any of it later on the Profile page.">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[10rem_1fr]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="font-medium">{v}</dd>
          </div>
        ))}
      </dl>
      {profile.setup.missing.length > 0 && (
        <Alert tone="warning" title="Still needed">
          {profile.setup.missing.join(", ")}.
        </Alert>
      )}
    </Section>
  );
}

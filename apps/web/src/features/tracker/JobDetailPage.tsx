"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ChevronLeft, Trash2 } from "lucide-react";

import { button, card, input, muted, primaryButton } from "@/components/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  ContactKind,
  EmailMode,
  JobDetail,
  PortalMode,
  Region,
  WorkMode,
} from "@/lib/api/types";

import {
  useAddContact,
  useDeleteContact,
  useDeleteJob,
  useJob,
  useUpdateApplication,
  useUpdateJob,
} from "./hooks";
import { ResearchSection } from "../research/ResearchSection";
import { StatusSelect, useStatusChanger } from "./StatusChanger";
import { STATUSES } from "./status";

const PORTAL_MODES: PortalMode[] = ["Not yet", "Done", "Not available"];
const EMAIL_MODES: EmailMode[] = ["Not yet", "Draft ready", "Sent", "No email found"];
const WORK_MODES: WorkMode[] = ["Remote", "Hybrid", "Onsite"];
const REGIONS: Region[] = ["India", "Europe", "USA", "UAE / Middle East", "Remote (Global)"];
const CONTACT_KINDS: ContactKind[] = ["published_business", "recruiter", "referral"];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1 text-sm">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const job = useJob(id);
  const changer = useStatusChanger();
  const remove = useDeleteJob();
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (job.isPending) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading job">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (job.isError) {
    return (
      <div className="flex flex-col gap-3">
        <ErrorState title="Could not load this job" description={job.error.message} onRetry={() => void job.refetch()} />
        <Link href="/jobs" className="text-sm text-accent-text underline">
          Back to jobs
        </Link>
      </div>
    );
  }
  const data = job.data;

  return (
    <div className="flex flex-col gap-5">
      <Link
        href="/jobs"
        className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft className="size-4" aria-hidden="true" /> All jobs
      </Link>

      <header className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">
          {data.company.name} <span className="font-normal text-muted-foreground">· {data.title}</span>
        </h1>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <StatusSelect
            job={data}
            statuses={STATUSES}
            label="Change status"
            onChange={(status) => changer.request(data, status)}
          />
          <nav aria-label="Links" className="flex gap-4 text-sm">
            {data.apply_url && <ExternalLink href={data.apply_url}>Apply</ExternalLink>}
            {data.jd_url && <ExternalLink href={data.jd_url}>Job description</ExternalLink>}
            {data.careers_url && <ExternalLink href={data.careers_url}>Careers page</ExternalLink>}
          </nav>
        </div>
        {changer.error && (
          <p role="alert" className="text-sm text-danger-text">
            {changer.error}
          </p>
        )}
      </header>

      <Tabs defaultValue="overview">
        <TabsList className="max-w-full overflow-x-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="research">Research</TabsTrigger>
          <TabsTrigger value="description">Description</TabsTrigger>
          <TabsTrigger value="edit">Edit</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="flex flex-col gap-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <ApplicationPanel key={data.application.updated_at} job={data} />
            <Timeline job={data} />
          </div>
          <Facts job={data} />
          <ContactsPanel job={data} />
        </TabsContent>

        <TabsContent value="research">
          <ResearchSection job={data} />
        </TabsContent>

        <TabsContent value="description">
          {data.jd_text ? (
            <section className={card}>
              <pre className="whitespace-pre-wrap font-sans text-sm">{data.jd_text}</pre>
            </section>
          ) : (
            <EmptyState
              title="No description saved"
              description="Paste the job posting under Edit to read its skills and check the company."
            />
          )}
        </TabsContent>

        <TabsContent value="edit" className="flex flex-col gap-6">
          <section className={card}>
            <EditJobForm key={data.updated_at} job={data} />
          </section>
          <section className="flex items-center justify-between gap-4 rounded-lg border border-danger/40 p-4">
            <div>
              <h2 className="font-medium">Delete this job</h2>
              <p className="text-sm text-muted-foreground">Removes the job, its history and contacts. This cannot be undone.</p>
            </div>
            <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
              <Trash2 aria-hidden="true" /> Delete job
            </Button>
          </section>
        </TabsContent>
      </Tabs>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this job?</DialogTitle>
            <DialogDescription>
              {data.title} at {data.company.name} and its history will be removed. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setConfirmDelete(false)}>Cancel</Button>
            <Button
              variant="destructive"
              loading={remove.isPending}
              onClick={() => remove.mutate(data.id, { onSuccess: () => router.replace("/jobs") })}
            >
              Delete job
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {changer.dialog}
    </div>
  );
}

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
      {children}
    </a>
  );
}

function Facts({ job }: { job: JobDetail }) {
  const rows: [string, string | null | undefined][] = [
    ["Region", job.region],
    ["Location", job.location_text],
    ["Work mode", job.work_mode],
    ["Job type", job.job_type],
    ["Salary (as posted)", job.salary_text],
    ["Est. CTC", job.est_ctc_lpa ? `${job.est_ctc_lpa} LPA` : null],
    ["Hiring from India", job.hiring_from_india],
    ["Visa / relocation", job.visa],
    ["Posted", job.posted_on],
    ["Found", job.found_on],
    ["Source", job.source],
  ];
  return (
    <section className={card}>
      <h2 className="mb-2 font-semibold">Details</h2>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className={muted}>{label}</dt>
            <dd>{value || "-"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Timeline({ job }: { job: JobDetail }) {
  return (
    <section className={card}>
      <h2 className="mb-2 font-semibold">History</h2>
      <ol className="space-y-2 text-sm">
        {[...job.events].reverse().map((event) => (
          <li key={event.id}>
            <div>
              {event.from_status ? `${event.from_status} → ` : ""}
              <strong>{event.to_status}</strong>
              {event.type === "reopened" && <span className={muted}> (reopened)</span>}
            </div>
            <div className={muted}>{new Date(event.at).toLocaleString("en-GB")}</div>
            {event.note && <div>{event.note}</div>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function ApplicationPanel({ job }: { job: JobDetail }) {
  const update = useUpdateApplication();
  const app = job.application;
  const [portal, setPortal] = useState(app.portal_mode);
  const [site, setSite] = useState(app.site_mode);
  const [email, setEmail] = useState(app.email_mode);
  const [followup, setFollowup] = useState(app.next_followup_on ?? "");
  const [resume, setResume] = useState(app.resume_version ?? "");
  const [notes, setNotes] = useState(app.notes ?? "");

  return (
    <form
      className={`${card} space-y-3`}
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate({
          applicationId: app.id,
          body: {
            portal_mode: portal,
            site_mode: site,
            email_mode: email,
            next_followup_on: followup || null,
            resume_version: resume.trim() || null,
            notes: notes.trim() || null,
          },
        });
      }}
    >
      <h2 className="font-semibold">Application</h2>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Job portal">
          <select value={portal} onChange={(e) => setPortal(e.target.value as PortalMode)} className={input}>
            {PORTAL_MODES.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Company site">
          <select value={site} onChange={(e) => setSite(e.target.value as PortalMode)} className={input}>
            {PORTAL_MODES.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Email">
          <select value={email} onChange={(e) => setEmail(e.target.value as EmailMode)} className={input}>
            {EMAIL_MODES.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Next follow-up">
          <input type="date" value={followup} onChange={(e) => setFollowup(e.target.value)} className={input} />
        </Field>
        <Field label="Resume used">
          <input value={resume} onChange={(e) => setResume(e.target.value)} className={input} />
        </Field>
      </div>
      <p className={muted}>Applied on: {app.applied_on ?? "not yet"}</p>
      <Field label="Notes">
        <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className={input} />
      </Field>
      <p role="alert" className="min-h-5 text-sm text-danger-text">
        {update.error?.message}
      </p>
      <button type="submit" disabled={update.isPending} className={primaryButton}>
        {update.isPending ? "Saving..." : "Save"}
      </button>
    </form>
  );
}

function EditJobForm({ job }: { job: JobDetail }) {
  const update = useUpdateJob(job.id);
  const [form, setForm] = useState({
    title: job.title,
    location_text: job.location_text ?? "",
    region: job.region ?? "",
    work_mode: job.work_mode ?? "",
    est_ctc_lpa: job.est_ctc_lpa?.toString() ?? "",
    salary_text: job.salary_text ?? "",
    apply_url: job.apply_url ?? "",
    jd_url: job.jd_url ?? "",
    careers_url: job.careers_url ?? "",
    jd_text: job.jd_text ?? "",
  });
  const set = (name: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [name]: event.target.value }));
  const orNull = (value: string) => value.trim() || null;

  return (
    <form
      className="mt-3 space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate({
          title: form.title,
          location_text: orNull(form.location_text),
          region: (orNull(form.region) as Region | null) ?? null,
          work_mode: (orNull(form.work_mode) as WorkMode | null) ?? null,
          est_ctc_lpa: form.est_ctc_lpa ? Number(form.est_ctc_lpa) : null,
          salary_text: orNull(form.salary_text),
          apply_url: orNull(form.apply_url),
          jd_url: orNull(form.jd_url),
          careers_url: orNull(form.careers_url),
          jd_text: orNull(form.jd_text),
        });
      }}
    >
      <div className="grid grid-cols-2 gap-3">
        <Field label="Role"><input required value={form.title} onChange={set("title")} className={input} /></Field>
        <Field label="Location"><input value={form.location_text} onChange={set("location_text")} className={input} /></Field>
        <Field label="Region">
          <select value={form.region} onChange={set("region")} className={input}>
            <option value="">-</option>
            {REGIONS.map((r) => <option key={r}>{r}</option>)}
          </select>
        </Field>
        <Field label="Work mode">
          <select value={form.work_mode} onChange={set("work_mode")} className={input}>
            <option value="">-</option>
            {WORK_MODES.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Est. CTC (LPA)"><input type="number" min="0" step="0.1" value={form.est_ctc_lpa} onChange={set("est_ctc_lpa")} className={input} /></Field>
        <Field label="Salary as posted"><input value={form.salary_text} onChange={set("salary_text")} className={input} /></Field>
        <Field label="Apply link"><input type="url" value={form.apply_url} onChange={set("apply_url")} className={input} /></Field>
        <Field label="Job description link"><input type="url" value={form.jd_url} onChange={set("jd_url")} className={input} /></Field>
        <Field label="Careers page"><input type="url" value={form.careers_url} onChange={set("careers_url")} className={input} /></Field>
      </div>
      <Field label="Job description text">
        <textarea rows={6} value={form.jd_text} onChange={set("jd_text")} className={input} />
      </Field>
      <p role="alert" className="min-h-5 text-sm text-danger-text">{update.error?.message}</p>
      <button type="submit" disabled={update.isPending} className={primaryButton}>
        {update.isPending ? "Saving..." : "Save details"}
      </button>
    </form>
  );
}

function ContactsPanel({ job }: { job: JobDetail }) {
  const add = useAddContact(job.id);
  const remove = useDeleteContact(job.id);
  const [form, setForm] = useState({ name: "", role: "", email: "", phone: "", kind: "recruiter" as ContactKind, source_url: "" });
  const set = (name: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [name]: event.target.value }));

  return (
    <section className={`${card} space-y-3`}>
      <h2 className="font-semibold">Contacts</h2>
      <p className={muted}>
        Only add contact details a company has published itself, with the page where you found them.
      </p>
      {job.contacts.length === 0 && <p className={muted}>No contacts yet.</p>}
      <ul className="space-y-2 text-sm">
        {job.contacts.map((contact) => (
          <li key={contact.id} className="flex items-start justify-between gap-3">
            <div>
              <div className="font-medium">
                {contact.name} {contact.role && <span className="font-normal text-muted-foreground">· {contact.role}</span>}
              </div>
              <div>{[contact.email, contact.phone].filter(Boolean).join(" · ")}</div>
              <div className={muted}>
                {contact.kind.replace("_", " ")}
                {contact.source_url && (
                  <>
                    {" · "}
                    <ExternalLink href={contact.source_url}>source</ExternalLink>
                  </>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => remove.mutate(contact.id)}
              aria-label={`Delete contact ${contact.name}`}
              className={button}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
      <form
        className="grid grid-cols-2 gap-3 border-t border-border-subtle pt-3"
        onSubmit={(event) => {
          event.preventDefault();
          const text = (value: string) => value.trim() || undefined;
          add.mutate(
            {
              name: form.name,
              role: text(form.role),
              email: text(form.email),
              phone: text(form.phone),
              kind: form.kind,
              source_url: text(form.source_url),
            },
            { onSuccess: () => setForm({ ...form, name: "", role: "", email: "", phone: "", source_url: "" }) },
          );
        }}
      >
        <Field label="Name"><input required value={form.name} onChange={set("name")} className={input} /></Field>
        <Field label="Role"><input value={form.role} onChange={set("role")} className={input} /></Field>
        <Field label="Email"><input type="email" value={form.email} onChange={set("email")} className={input} /></Field>
        <Field label="Phone"><input value={form.phone} onChange={set("phone")} className={input} /></Field>
        <Field label="Kind">
          <select value={form.kind} onChange={set("kind")} className={input}>
            {CONTACT_KINDS.map((k) => <option key={k} value={k}>{k.replace("_", " ")}</option>)}
          </select>
        </Field>
        <Field label="Source page (required for published)">
          <input type="url" value={form.source_url} onChange={set("source_url")} className={input} />
        </Field>
        <p role="alert" className="col-span-2 min-h-5 text-sm text-danger-text">{add.error?.message}</p>
        <div className="col-span-2">
          <button type="submit" disabled={add.isPending} className={primaryButton}>Add contact</button>
        </div>
      </form>
    </section>
  );
}

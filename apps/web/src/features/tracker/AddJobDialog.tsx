"use client";

import Link from "next/link";
import { useState } from "react";

import { Modal } from "@/components/Modal";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { Alert } from "@/components/ui/states";
import type { JobCreate, Region, WorkMode } from "@/lib/api/types";

import { useCreateJob } from "./hooks";

const REGIONS: Region[] = ["India", "Europe", "USA", "UAE / Middle East", "Remote (Global)"];
const MODES: WorkMode[] = ["Remote", "Hybrid", "Onsite"];

const EMPTY = {
  company_name: "",
  title: "",
  location_text: "",
  region: "",
  work_mode: "",
  apply_url: "",
  jd_url: "",
  est_ctc_lpa: "",
  jd_text: "",
};

export function AddJobDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateJob();
  const [form, setForm] = useState(EMPTY);
  const [existing, setExisting] = useState<{ id: string } | null>(null);

  const set = (name: keyof typeof EMPTY) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [name]: event.target.value }));

  function close() {
    setForm(EMPTY);
    setExisting(null);
    create.reset();
    onClose();
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = (value: string) => value.trim() || undefined;
    const body: JobCreate = {
      company_name: form.company_name,
      title: form.title,
      location_text: text(form.location_text),
      region: (text(form.region) as Region | undefined) ?? undefined,
      work_mode: (text(form.work_mode) as WorkMode | undefined) ?? undefined,
      apply_url: text(form.apply_url),
      jd_url: text(form.jd_url),
      est_ctc_lpa: form.est_ctc_lpa ? Number(form.est_ctc_lpa) : undefined,
      jd_text: text(form.jd_text),
    };
    create.mutate(body, {
      onSuccess: ({ job, existed }) => {
        if (existed) setExisting(job);
        else close();
      },
    });
  }

  return (
    <Modal open={open} onClose={close} title="Add a job">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Company" required>
            {(p) => <Input required value={form.company_name} onChange={set("company_name")} {...p} />}
          </Field>
          <Field label="Role" required>
            {(p) => <Input required value={form.title} onChange={set("title")} {...p} />}
          </Field>
          <Field label="Location">
            {(p) => <Input value={form.location_text} onChange={set("location_text")} {...p} />}
          </Field>
          <Field label="Est. CTC (LPA)">
            {(p) => (
              <Input type="number" min="0" step="0.1" value={form.est_ctc_lpa} onChange={set("est_ctc_lpa")} {...p} />
            )}
          </Field>
          <Field label="Region">
            {(p) => (
              <Select value={form.region} onChange={set("region")} {...p}>
                <option value="">-</option>
                {REGIONS.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Work mode">
            {(p) => (
              <Select value={form.work_mode} onChange={set("work_mode")} {...p}>
                <option value="">-</option>
                {MODES.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </Select>
            )}
          </Field>
        </div>
        <Field label="Apply link">
          {(p) => <Input type="url" value={form.apply_url} onChange={set("apply_url")} {...p} />}
        </Field>
        <Field label="Job description link">
          {(p) => <Input type="url" value={form.jd_url} onChange={set("jd_url")} {...p} />}
        </Field>
        <Field label="Job description text" help="Paste the posting. It is used to read skills and check the company.">
          {(p) => <Textarea rows={4} value={form.jd_text} onChange={set("jd_text")} {...p} />}
        </Field>

        {existing && (
          <Alert tone="info">
            Already tracked.{" "}
            <Link href={`/jobs/${existing.id}`} className="font-medium underline">
              Open it
            </Link>
          </Alert>
        )}
        <p role="alert" className="min-h-5 text-sm text-danger-text">
          {create.error?.message}
        </p>
        <div className="flex justify-end gap-2">
          <Button onClick={close}>Close</Button>
          <Button type="submit" variant="primary" loading={create.isPending}>
            Add job
          </Button>
        </div>
      </form>
    </Modal>
  );
}

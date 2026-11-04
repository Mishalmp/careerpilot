"use client";

import Link from "next/link";
import { useState } from "react";

import { Modal } from "@/components/Modal";
import { button, input, muted, primaryButton } from "@/components/ui";
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
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-sm">
            <span>Company *</span>
            <input required value={form.company_name} onChange={set("company_name")} className={input} />
          </label>
          <label className="space-y-1 text-sm">
            <span>Role *</span>
            <input required value={form.title} onChange={set("title")} className={input} />
          </label>
          <label className="space-y-1 text-sm">
            <span>Location</span>
            <input value={form.location_text} onChange={set("location_text")} className={input} />
          </label>
          <label className="space-y-1 text-sm">
            <span>Est. CTC (LPA)</span>
            <input type="number" min="0" step="0.1" value={form.est_ctc_lpa} onChange={set("est_ctc_lpa")} className={input} />
          </label>
          <label className="space-y-1 text-sm">
            <span>Region</span>
            <select value={form.region} onChange={set("region")} className={input}>
              <option value="">-</option>
              {REGIONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span>Work mode</span>
            <select value={form.work_mode} onChange={set("work_mode")} className={input}>
              <option value="">-</option>
              {MODES.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="block space-y-1 text-sm">
          <span>Apply link</span>
          <input type="url" value={form.apply_url} onChange={set("apply_url")} className={input} />
        </label>
        <label className="block space-y-1 text-sm">
          <span>Job description link</span>
          <input type="url" value={form.jd_url} onChange={set("jd_url")} className={input} />
        </label>
        <label className="block space-y-1 text-sm">
          <span>Job description text</span>
          <textarea rows={4} value={form.jd_text} onChange={set("jd_text")} className={input} />
        </label>

        {existing && (
          <p role="status" className={muted}>
            Already tracked. <Link href={`/jobs/${existing.id}`} className="underline">Open it</Link>
          </p>
        )}
        <p role="alert" className="min-h-5 text-sm text-red-600 dark:text-red-400">
          {create.error?.message}
        </p>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={close} className={button}>
            Close
          </button>
          <button type="submit" disabled={create.isPending} className={primaryButton}>
            {create.isPending ? "Adding..." : "Add job"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

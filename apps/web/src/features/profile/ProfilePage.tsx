"use client";

import { ArrowLeft, ArrowRight, PartyPopper, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { ProgressBar, Stepper } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, ErrorState } from "@/components/ui/states";

import { changes, type Draft, toDraft } from "./draft";
import { type Profile, useCompleteSetup, useProfile, useUpdateProfile } from "./hooks";
import { AboutSection, CvSection, GoalsSection, LinksSection, ReadSection, ReviewSection } from "./sections";

const STEPS = ["About you", "What you want", "Your CV", "Public profiles", "Review"];

/**
 * Account setup. Nobody's details are built in: you say who you are and what you want, add a CV,
 * and everything else (scoring, research, the daily apply list) is aimed from that.
 * Until setup is finished this is a short wizard; afterwards the same sections are one page.
 */
export function ProfilePage() {
  const profile = useProfile();
  if (profile.isPending) return <Skeleton className="h-64" aria-busy="true" aria-label="Loading profile" />;
  if (profile.isError) {
    return <ErrorState title="Could not load your profile" description={profile.error.message} onRetry={() => void profile.refetch()} />;
  }
  const p = profile.data;
  // The one-page view remounts after each save so its form starts clean; the wizard must not, or it
  // would jump back to the first step.
  return p.setup.complete ? <Settings key={p.updated_at ?? "none"} profile={p} /> : <Wizard profile={p} />;
}

/** What is on screen: the saved profile with your unsaved edits on top. */
function useDraft(profile: Profile) {
  const [edits, setEdits] = useState<Partial<Draft>>({});
  const draft: Draft = { ...toDraft(profile), ...edits };
  const edit = (patch: Partial<Draft>) => setEdits((e) => ({ ...e, ...patch }));
  return { draft, edit, pending: changes(profile, draft, new Set(Object.keys(edits))) };
}

function Wizard({ profile }: { profile: Profile }) {
  const router = useRouter();
  const update = useUpdateProfile();
  const complete = useCompleteSetup();
  const { draft, edit, pending } = useDraft(profile);
  const [step, setStep] = useState(0);
  const dirty = Object.keys(pending).length > 0;
  const error = update.error ?? complete.error;

  const next = async () => {
    try {
      if (dirty) await update.mutateAsync(pending);
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    } catch {
      // the error is shown below; stay on this step so nothing typed is lost
    }
  };
  const finish = async () => {
    if (dirty) await update.mutateAsync(pending);
    await complete.mutateAsync();
    router.push("/");
  };

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
      <PageHeader title="Set up your account" description="A few questions so CareerPilot works for you and not for someone else. It takes about three minutes, and you can change everything later." />
      <ProgressBar label="Setup progress" value={(step / (STEPS.length - 1)) * 100} />
      <Stepper steps={STEPS} current={step} onSelect={setStep} />

      {step === 0 && <AboutSection draft={draft} edit={edit} />}
      {step === 1 && <GoalsSection draft={draft} edit={edit} suggestions={profile.role_titles} />}
      {step === 2 && (
        <>
          <CvSection profile={profile} />
          {(profile.skills.length > 0 || profile.role_titles.length > 0) && <ReadSection profile={profile} />}
        </>
      )}
      {step === 3 && <LinksSection draft={draft} edit={edit} profile={profile} />}
      {step === 4 && <ReviewSection profile={profile} />}

      {error && (
        <p role="alert" className="text-sm text-danger-text">
          {error.message}
        </p>
      )}
      <div className="flex items-center justify-between gap-2 border-t border-border-subtle pt-4">
        <Button variant="ghost" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          <ArrowLeft aria-hidden="true" /> Back
        </Button>
        {step < STEPS.length - 1 ? (
          <Button variant="primary" onClick={() => void next()} loading={update.isPending}>
            {dirty ? "Save and continue" : "Continue"} <ArrowRight aria-hidden="true" />
          </Button>
        ) : (
          <Button variant="primary" onClick={() => void finish()} loading={complete.isPending || update.isPending} disabled={profile.setup.missing.length > 0 && !dirty}>
            <PartyPopper aria-hidden="true" /> Finish setup
          </Button>
        )}
      </div>
    </div>
  );
}

function Settings({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  const { draft, edit, pending } = useDraft(profile);
  const dirty = Object.keys(pending).length > 0;
  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Your profile"
        description="Everything the app knows about you. Scoring, research and your daily apply list are aimed from this, so keep it true."
      />
      {update.isSuccess && !dirty && <Alert tone="success">Saved.</Alert>}
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <div className="flex flex-col gap-5">
          <AboutSection draft={draft} edit={edit} />
          <GoalsSection draft={draft} edit={edit} suggestions={profile.role_titles} />
          <LinksSection draft={draft} edit={edit} profile={profile} />
        </div>
        <div className="flex flex-col gap-5">
          <CvSection profile={profile} />
          <ReadSection profile={profile} />
        </div>
      </div>
      <div className="sticky bottom-0 -mx-4 flex items-center justify-between gap-3 border-t border-border-subtle bg-background/95 px-4 py-3 backdrop-blur md:-mx-6 md:px-6">
        <p className="text-sm text-muted-foreground" role="status">
          {update.error ? <span className="text-danger-text">{update.error.message}</span> : dirty ? "You have unsaved changes." : "All changes are saved."}
        </p>
        <Button variant="primary" disabled={!dirty} loading={update.isPending} onClick={() => update.mutate(pending)}>
          <Save aria-hidden="true" /> Save changes
        </Button>
      </div>
    </div>
  );
}

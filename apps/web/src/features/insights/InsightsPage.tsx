"use client";

import { card, muted } from "@/components/ui";

import { type Analytics, useAnalytics } from "./hooks";

function Rate({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <p className="text-2xl font-semibold">
        {value === null ? "n/a" : `${value}%`}
      </p>
      <p className={muted}>{label}</p>
    </div>
  );
}

function Bars({
  values,
  labels,
  unit,
}: {
  values: number[];
  labels: string[];
  unit: string;
}) {
  const max = Math.max(1, ...values);
  return (
    <div
      className="flex items-end gap-1"
      role="img"
      aria-label={`${unit}: ${values.join(", ")}`}
    >
      {values.map((v, i) => (
        <div
          key={labels[i]}
          className="flex flex-1 flex-col items-center gap-1"
        >
          <div
            className="w-full rounded-sm bg-foreground/70"
            style={{ height: `${Math.max(2, (v / max) * 64)}px` }}
            title={`${labels[i]}: ${v} ${unit}`}
          />
          <span className="text-[10px] text-zinc-500">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}

function Funnel({ data }: { data: Analytics["funnel"] }) {
  const steps = [
    ["Tracked", data.tracked],
    ["Applied", data.applied],
    ["Heard back", data.responded],
    ["Interviewed", data.interviewed],
    ["Offers", data.offered],
  ] as const;
  const top = Math.max(1, data.tracked);
  return (
    <section className={`${card} space-y-3`} aria-labelledby="funnel-heading">
      <h2 id="funnel-heading" className="font-semibold">
        Application funnel
      </h2>
      <ul className="space-y-1">
        {steps.map(([label, count]) => (
          <li key={label} className="flex items-center gap-2 text-sm">
            <span className="w-24">{label}</span>
            <div className="h-3 flex-1 rounded-sm bg-black/5 dark:bg-white/10">
              <div
                className="h-3 rounded-sm bg-foreground/70"
                style={{ width: `${(count / top) * 100}%` }}
              />
            </div>
            <span className="w-8 text-right">{count}</span>
          </li>
        ))}
      </ul>
      <div className="grid grid-cols-3 gap-3">
        <Rate label="heard back" value={data.response_rate} />
        <Rate label="reached an interview" value={data.interview_rate} />
        <Rate label="reached an offer" value={data.offer_rate} />
      </div>
      <p className={muted}>
        {data.rejected} rejected, {data.no_response} never answered. Rates are
        shares of applications.
        {data.small_sample &&
          " With fewer than 10 applications they move a lot from one reply."}
      </p>
    </section>
  );
}

export function InsightsPage() {
  const query = useAnalytics();
  if (query.isPending) return <p className={muted}>Loading...</p>;
  if (query.isError)
    return <p role="alert">Could not load insights: {query.error.message}</p>;
  const {
    funnel,
    weekly_applications: weeks,
    prep,
    mocks,
    calibration,
    note,
  } = query.data;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Insights</h1>
      <p className={muted}>{note}</p>
      <Funnel data={funnel} />

      <section className={`${card} space-y-2`} aria-labelledby="pace-heading">
        <h2 id="pace-heading" className="font-semibold">
          Applications per week
        </h2>
        <Bars
          values={weeks.map((w) => w.applications)}
          labels={weeks.map((w) => w.week_start.slice(5))}
          unit="applications"
        />
      </section>

      <section className={`${card} space-y-3`} aria-labelledby="prep-heading">
        <h2 id="prep-heading" className="font-semibold">
          Preparation
        </h2>
        <p className="text-sm">
          {prep.total_minutes} minutes over {prep.study_days} of the last 14
          days
          {prep.average_confidence !== null &&
            `; average confidence ${prep.average_confidence}/5`}
          .
        </p>
        <Bars
          values={prep.minutes_by_day.map((d) => d.minutes)}
          labels={prep.minutes_by_day.map((d) => d.day.slice(8))}
          unit="minutes"
        />
        <p className={muted}>
          Topics:{" "}
          {Object.entries(prep.topics)
            .map(([status, count]) => `${count} ${status.toLowerCase()}`)
            .join(", ") || "none loaded yet"}
          .
        </p>
        {mocks.length > 0 && (
          <>
            <h3 className="text-sm font-semibold">
              Mock interview averages (out of 5)
            </h3>
            <Bars
              values={mocks.map((m) => m.average)}
              labels={mocks.map((m) => m.day.slice(5))}
              unit="out of 5"
            />
          </>
        )}
      </section>

      <section
        className={`${card} space-y-2`}
        aria-labelledby="calibration-heading"
      >
        <h2 id="calibration-heading" className="font-semibold">
          Does the fit score predict interviews?
        </h2>
        <p className="text-sm">{calibration.explanation}</p>
        {calibration.groups.length === 0 ? (
          <p className={muted}>No jobs have been scored yet.</p>
        ) : (
          <table className="w-full text-sm">
            <caption className="sr-only">Interviews by fit label</caption>
            <thead>
              <tr className="text-left text-zinc-500">
                <th>Label</th>
                <th>Scored</th>
                <th>Outcome known</th>
                <th>Interviewed</th>
                <th>Rate</th>
              </tr>
            </thead>
            <tbody>
              {calibration.groups.map((g) => (
                <tr
                  key={g.chance}
                  className="border-t border-black/5 dark:border-white/10"
                >
                  <td className="capitalize">{g.chance}</td>
                  <td>{g.scored}</td>
                  <td>{g.decided}</td>
                  <td>{g.interviewed}</td>
                  <td>
                    {g.interview_rate === null ? "n/a" : `${g.interview_rate}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

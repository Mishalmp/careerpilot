"use client";

import { useState } from "react";

import { button, card, input, muted, primaryButton, select } from "@/components/ui";
import type { Day, DayStatus } from "@/lib/api/types";

import { useDays, useSeedPrep, useSetStartDate, useUpdateDay } from "./hooks";
import { PrepNav } from "./PrepNav";

const DAY_STATUSES: DayStatus[] = ["Planned", "Done", "Skipped", "Moved"];
const todayLocal = () => new Date().toLocaleDateString("en-CA");

export function RoadmapPage() {
  const days = useDays();
  const seed = useSeedPrep();
  const setStart = useSetStartDate();
  const [start, setStartInput] = useState("");

  const data = days.data ?? [];
  const configured = data.some((d) => d.scheduled_on);
  const today = todayLocal();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Prep</h1>
      <PrepNav />

      {days.isPending && <p className={muted}>Loading...</p>}
      {days.isSuccess && data.length === 0 && (
        <div className={`${card} space-y-2`}>
          <p>The 45-day plan and its 159 topics are not loaded yet.</p>
          <button type="button" onClick={() => seed.mutate()} disabled={seed.isPending} className={primaryButton}>
            {seed.isPending ? "Loading..." : "Load the curriculum"}
          </button>
          {seed.error && <p role="alert" className="text-red-600">{seed.error.message}</p>}
        </div>
      )}

      {data.length > 0 && (
        <>
          <form
            className="flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (start) setStart.mutate(start);
            }}
          >
            <label className="space-y-1 text-sm">
              <span>{configured ? "Day 1 is" : "Choose the date for day 1"}</span>
              <input
                type="date"
                required
                value={start || data[0]?.scheduled_on || ""}
                onChange={(event) => setStartInput(event.target.value)}
                className={input}
              />
            </label>
            <button type="submit" disabled={!start || setStart.isPending} className={button}>
              {configured ? "Change start date" : "Start the plan"}
            </button>
          </form>

          <ol className="space-y-2">
            {data.map((day) => (
              <DayRow key={day.day} day={day} isToday={day.scheduled_on === today} />
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function DayRow({ day, isToday }: { day: Day; isToday: boolean }) {
  const update = useUpdateDay();
  return (
    <li className={`${card} ${isToday ? "border-foreground" : ""}`}>
      <details open={isToday}>
        <summary className="flex cursor-pointer flex-wrap items-center gap-3">
          <strong>Day {day.day}</strong>
          <span className={muted}>{day.scheduled_on ?? "no date yet"}</span>
          <span className="font-medium">{day.focus}</span>
          <span className={`${muted} ml-auto`}>
            {day.phase} · {day.hours} h · {day.status}
          </span>
        </summary>
        <div className="mt-3 space-y-2 text-sm">
          <p><strong>Learn:</strong> {day.core_topics}</p>
          <p><strong>Practise:</strong> {day.practice}</p>
          <p><strong>Say aloud:</strong> {day.speaking}</p>
          <p><strong>Deliverable:</strong> {day.deliverable}</p>
          <label className="flex items-center gap-2">
            <span>Status</span>
            <select
              value={day.status}
              onChange={(event) =>
                update.mutate({ day: day.day, status: event.target.value as DayStatus })
              }
              className={select}
            >
              {DAY_STATUSES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
      </details>
    </li>
  );
}

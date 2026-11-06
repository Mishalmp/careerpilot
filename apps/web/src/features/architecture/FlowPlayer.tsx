"use client";

import { ChevronLeft, ChevronRight, Pause, Play, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { DiagramCanvas } from "./DiagramCanvas";
import type { Diagram, Flow } from "./hooks";

/** Plays one flow step by step over the overview diagram, with "what if this fails" branches. */
export function FlowPlayer({ flows, overview }: { flows: Flow[]; overview: Diagram }) {
  const [flowId, setFlowId] = useState(flows[0]?.id ?? "");
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [showFailure, setShowFailure] = useState(false);
  const flow = flows.find((f) => f.id === flowId) ?? flows[0];

  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const last = (flow?.steps.length ?? 1) - 1;

  // Auto-play advances every 4 seconds and stops at the end. Off when the user prefers less motion.
  useEffect(() => {
    if (!playing || reduced) return;
    const timer = setInterval(() => {
      setStep((s) => {
        if (s >= last) {
          setPlaying(false);
          return s;
        }
        setShowFailure(false);
        return s + 1;
      });
    }, 4000);
    return () => clearInterval(timer);
  }, [playing, reduced, last]);

  const current = flow?.steps[step];
  const highlight = useMemo(() => (current ? [current.source, current.target] : []), [current]);

  if (!flow || !current) return null;

  function go(next: number) {
    setStep(Math.min(last, Math.max(0, next)));
    setShowFailure(false);
  }
  function choose(id: string) {
    setFlowId(id);
    setStep(0);
    setPlaying(false);
    setShowFailure(false);
  }

  return (
    <div
      className="flex flex-col gap-4"
      onKeyDown={(e) => {
        if (e.target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName)) return;
        if (e.key === "ArrowRight") go(step + 1);
        if (e.key === "ArrowLeft") go(step - 1);
      }}
    >
      <div role="tablist" aria-label="Flows" className="flex flex-wrap gap-2">
        {flows.map((f) => (
          <button
            key={f.id}
            role="tab"
            aria-selected={f.id === flow.id}
            onClick={() => choose(f.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-[0.8125rem] font-medium transition-colors",
              f.id === flow.id
                ? "border-primary bg-accent-soft text-accent-text"
                : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            {f.title}
            {f.status === "planned" ? " (planned)" : ""}
          </button>
        ))}
      </div>

      <p className="max-w-3xl text-sm text-muted-foreground">{flow.summary}</p>

      <DiagramCanvas
        diagram={{ ...overview, title: flow.title, summary: "The highlighted parts and arrow are the current step." }}
        highlightNodes={highlight}
        highlightEdge={{ source: current.source, target: current.target }}
        height={380}
      />

      <section
        aria-live="polite"
        aria-label={`Step ${step + 1} of ${flow.steps.length}`}
        className="rounded-lg border border-border-subtle bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-medium text-muted-foreground">
            Step {step + 1} of {flow.steps.length}
          </p>
          {flow.status === "planned" && <Badge tone="warning">Planned, not built yet</Badge>}
        </div>
        <h3 className="mt-1 text-base font-semibold">{current.label}</h3>
        <p className="mt-1 text-[length:var(--text-base)]">{current.detail}</p>

        {current.failure && (
          <div className="mt-3">
            <Button size="sm" variant="soft" aria-expanded={showFailure} onClick={() => setShowFailure((v) => !v)}>
              <TriangleAlert aria-hidden="true" /> What if this fails?
            </Button>
            {showFailure && (
              <div role="note" className="mt-2 rounded-md border border-warning/40 bg-warning-soft p-3 text-sm text-warning-text">
                <p className="font-medium">{current.failure.label}</p>
                <p className="mt-0.5">{current.failure.detail}</p>
              </div>
            )}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={() => go(step - 1)} disabled={step === 0}>
            <ChevronLeft aria-hidden="true" /> Back
          </Button>
          <Button size="sm" variant="primary" onClick={() => go(step + 1)} disabled={step === last}>
            Next <ChevronRight aria-hidden="true" />
          </Button>
          {!reduced && (
            <Button size="sm" variant="ghost" onClick={() => setPlaying((p) => !p)}>
              {playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />} {playing ? "Pause" : "Play"}
            </Button>
          )}
          <span className="ml-auto hidden text-xs text-muted-foreground sm:inline">Tip: arrow keys also step</span>
        </div>
      </section>

      {flow.proof.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Proven by:{" "}
          {flow.proof.map((p, i) => (
            <span key={p}>
              {i > 0 ? ", " : ""}
              <code className="rounded bg-surface-hover px-1.5 py-0.5">{p}</code>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

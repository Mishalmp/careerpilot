"use client";

import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { cn } from "@/lib/utils";

/** A list of short items you can remove or add to. `suggestions` are one click to add. */
export function TagInput({
  label,
  items,
  onChange,
  placeholder,
  busy = false,
  suggestions = [],
  emptyText = "None yet.",
}: {
  label: string;
  items: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
  busy?: boolean;
  suggestions?: string[];
  emptyText?: string;
}) {
  const [draft, setDraft] = useState("");
  const add = (value: string) => {
    const text = value.trim();
    if (text && !items.some((i) => i.toLowerCase() === text.toLowerCase())) onChange([...items, text]);
    setDraft("");
  };
  const offered = suggestions.filter((s) => !items.some((i) => i.toLowerCase() === s.toLowerCase())).slice(0, 8);
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-[0.8125rem] font-medium">{label}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5" aria-label={label}>
          {items.map((item) => (
            <li key={item} className="inline-flex items-center gap-1 rounded-full bg-accent-soft py-0.5 pl-2.5 pr-1 text-[0.8125rem] text-accent-text">
              {item}
              <button
                type="button"
                aria-label={`Remove ${item}`}
                disabled={busy}
                onClick={() => onChange(items.filter((i) => i !== item))}
                className="rounded-full p-0.5 transition-colors hover:bg-accent-soft-hover"
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          add(draft);
        }}
      >
        <Input aria-label={`Add to ${label}`} placeholder={placeholder} value={draft} onChange={(e) => setDraft(e.target.value)} className="max-w-xs" />
        <Button type="submit" disabled={busy || !draft.trim()}>
          <Plus aria-hidden="true" /> Add
        </Button>
      </form>
      {offered.length > 0 && (
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          Suggested:
          {offered.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className="rounded-full border border-dashed border-border px-2 py-0.5 text-[0.8125rem] text-foreground transition-colors hover:border-primary hover:bg-accent-soft hover:text-accent-text"
            >
              + {s}
            </button>
          ))}
        </p>
      )}
    </div>
  );
}

/** A fixed set of choices; any number can be on. Each is a real toggle button. */
export function ToggleChips({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly string[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <h3 id={`${label}-h`} className="text-[0.8125rem] font-medium">
        {label}
      </h3>
      <div role="group" aria-labelledby={`${label}-h`} className="flex flex-wrap gap-1.5">
        {options.map((option) => {
          const on = value.includes(option);
          return (
            <button
              key={option}
              type="button"
              aria-pressed={on}
              onClick={() => onChange(on ? value.filter((v) => v !== option) : [...value, option])}
              className={cn(
                "rounded-full border px-3 py-1 text-[0.8125rem] font-medium capitalize transition-colors",
                on ? "border-primary bg-accent-soft text-accent-text" : "border-border text-muted-foreground hover:bg-surface-hover hover:text-foreground",
              )}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

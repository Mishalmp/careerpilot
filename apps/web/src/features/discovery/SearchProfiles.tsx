"use client";

import { MapPin, Plus, SlidersHorizontal, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, Input } from "@/components/ui/field";
import { IconChip } from "@/components/ui/stat";
import { Switch } from "@/components/ui/switch";
import { TagInput, ToggleChips } from "@/features/profile/Chips";
import { REGIONS, WORK_MODES } from "@/features/profile/draft";

import {
  type NewSearchProfile,
  type SearchProfile,
  useCreateSearch,
  useDeleteSearch,
  useSearches,
  useToggleSearch,
} from "./searchHooks";

type Preset = { label: string; body: NewSearchProfile };

/** One click to add the searches most people want; every field can still be edited by adding a custom one. */
const PRESETS: Preset[] = [
  {
    label: "India: on site or hybrid in big cities",
    body: {
      name: "India on site or hybrid",
      regions: ["India"],
      cities: [
        "Bengaluru",
        "Hyderabad",
        "Pune",
        "Chennai",
        "Mumbai",
        "Delhi NCR",
      ],
      work_modes: ["Hybrid", "Onsite"],
    },
  },
  {
    label: "India: remote",
    body: { name: "India remote", regions: ["India"], work_modes: ["Remote"] },
  },
  {
    label: "Dubai: on site or remote",
    body: {
      name: "Dubai",
      regions: ["UAE / Middle East"],
      cities: ["Dubai"],
      work_modes: ["Onsite", "Remote"],
    },
  },
  {
    label: "Europe and USA: remote",
    body: {
      name: "Abroad remote",
      regions: ["Europe", "USA"],
      work_modes: ["Remote"],
    },
  },
];

export function SearchProfiles() {
  const searches = useSearches();
  const create = useCreateSearch();
  const toggle = useToggleSearch();
  const remove = useDeleteSearch();
  const error = create.error ?? toggle.error ?? remove.error;
  const have = new Set(searches.data?.map((s) => s.name));

  return (
    <Card>
      <CardHeader className="flex-row items-start gap-3">
        <IconChip icon={MapPin} tone="violet" />
        <div className="min-w-0">
          <CardTitle>Where and how I search</CardTitle>
          <CardDescription className="mt-1">
            Each search is one combination: regions, cities, and remote, hybrid
            or on site. A job is kept when it fits <strong>any</strong> of your
            searches. Cities take any spelling (Bangalore finds Bengaluru). With
            no search, nothing is filtered.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {searches.data?.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No searches yet: every listing is shown. Add one below.
          </p>
        )}
        <ul className="flex flex-col gap-2">
          {searches.data?.map((s) => (
            <SearchRow
              key={s.id}
              search={s}
              onToggle={(enabled) => toggle.mutate({ id: s.id, enabled })}
              onDelete={() => remove.mutate(s.id)}
              busy={toggle.isPending || remove.isPending}
            />
          ))}
        </ul>

        <div className="flex flex-col gap-2">
          <h3 className="text-[0.8125rem] font-medium">Add with one click</h3>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <Button
                key={p.label}
                size="sm"
                disabled={create.isPending || have.has(p.body.name)}
                onClick={() => create.mutate(p.body)}
              >
                <Plus aria-hidden="true" /> {p.label}
              </Button>
            ))}
          </div>
        </div>
        <CustomSearch
          onAdd={(body) => create.mutate(body)}
          busy={create.isPending}
        />
        {error && (
          <p role="alert" className="text-sm text-danger-text">
            {error.message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function SearchRow({
  search,
  onToggle,
  onDelete,
  busy,
}: {
  search: SearchProfile;
  onToggle: (on: boolean) => void;
  onDelete: () => void;
  busy: boolean;
}) {
  return (
    <li
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-subtle p-3"
      aria-label={`Search: ${search.name}`}
    >
      <div className="min-w-0">
        <p className="font-medium">{search.name}</p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {search.regions.map((r) => (
            <Badge key={r} tone="accent">
              {r}
            </Badge>
          ))}
          {search.cities.map((c) => (
            <Badge key={c} tone="neutral">
              {c}
            </Badge>
          ))}
          {search.work_modes.map((m) => (
            <Badge key={m} tone="outline">
              {m}
            </Badge>
          ))}
          {search.keywords.map((k) => (
            <Badge key={k} tone="success">
              title: {k}
            </Badge>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <Switch
            checked={search.enabled}
            disabled={busy}
            onCheckedChange={onToggle}
            aria-label={`Use ${search.name}`}
          />
          {search.enabled ? "On" : "Paused"}
        </label>
        <Button
          size="sm"
          variant="ghost"
          disabled={busy}
          onClick={onDelete}
          aria-label={`Delete search ${search.name}`}
        >
          <Trash2 aria-hidden="true" />
        </Button>
      </div>
    </li>
  );
}

function CustomSearch({
  onAdd,
  busy,
}: {
  onAdd: (body: NewSearchProfile) => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [regions, setRegions] = useState<string[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [modes, setModes] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  if (!open) {
    return (
      <div>
        <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
          <SlidersHorizontal aria-hidden="true" /> Build my own search
        </Button>
      </div>
    );
  }
  const ready = name.trim() !== "" && regions.length > 0 && modes.length > 0;
  const submit = () => {
    onAdd({
      name: name.trim(),
      regions: regions as NewSearchProfile["regions"],
      cities,
      work_modes: modes as NewSearchProfile["work_modes"],
      keywords,
    });
    setOpen(false);
    setName("");
    setRegions([]);
    setCities([]);
    setModes([]);
    setKeywords([]);
  };
  // Not a <form>: the city and word boxes are small forms of their own, and forms cannot nest
  // (pressing Enter in one would have sent this whole search half-finished).
  return (
    <div
      role="group"
      aria-label="Build my own search"
      className="flex flex-col gap-4 rounded-lg border border-border-subtle bg-surface-muted p-4"
    >
      <Field label="Name of this search" required>
        {(p) => (
          <Input
            placeholder="e.g. Bengaluru and Hyderabad, hybrid"
            value={name}
            onChange={(e) => setName(e.target.value)}
            {...p}
          />
        )}
      </Field>
      <ToggleChips
        label="Regions"
        options={REGIONS}
        value={regions}
        onChange={setRegions}
      />
      <TagInput
        label="Cities (for on site and hybrid)"
        items={cities}
        onChange={setCities}
        placeholder="e.g. Bangalore"
        emptyText="Any city in those regions."
      />
      <ToggleChips
        label="Ways of working"
        options={WORK_MODES}
        value={modes}
        onChange={setModes}
      />
      <TagInput
        label="Title must contain one of"
        items={keywords}
        onChange={setKeywords}
        placeholder="e.g. backend"
        emptyText="Any title."
      />
      <div className="flex gap-2">
        <Button
          type="button"
          variant="primary"
          disabled={!ready || busy}
          onClick={submit}
        >
          Add this search
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

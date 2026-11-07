import type { Profile, ProfileLink, ProfileUpdate } from "./hooks";

export const LINK_KINDS = [
  { kind: "linkedin", label: "LinkedIn", placeholder: "https://www.linkedin.com/in/your-name", note: "Shown to you only: LinkedIn is never read." },
  { kind: "github", label: "GitHub", placeholder: "https://github.com/your-name", note: "Optional: its public repositories can suggest skills." },
  { kind: "leetcode", label: "LeetCode", placeholder: "https://leetcode.com/u/your-name", note: "Optional. Kept as a link." },
  { kind: "naukri", label: "Naukri", placeholder: "https://www.naukri.com/mnjuser/profile", note: "Kept as a link: Naukri is never read." },
  { kind: "portfolio", label: "Portfolio or website", placeholder: "https://your-site.dev", note: "Optional." },
] as const;

export type LinkKind = (typeof LINK_KINDS)[number]["kind"];

export const LEVELS = ["junior", "mid", "senior", "lead"] as const;
export const REGIONS = ["India", "Europe", "USA", "UAE / Middle East", "Remote (Global)"] as const;
export const WORK_MODES = ["Remote", "Hybrid", "Onsite"] as const;

/** What the form holds while you type: text boxes keep text, even for numbers. */
export type Draft = {
  full_name: string;
  current_role: string;
  location: string;
  headline: string;
  years: string;
  target_roles: string[];
  target_levels: string[];
  regions: string[];
  work_modes: string[];
  needs_visa: boolean;
  salary_floor: string;
  salary_target: string;
  links: Record<LinkKind, string>;
};

const num = (value: number | null | undefined) => (value === null || value === undefined ? "" : String(value));

export function toDraft(p: Profile): Draft {
  const links = Object.fromEntries(LINK_KINDS.map((k) => [k.kind, ""])) as Record<LinkKind, string>;
  for (const link of p.links) links[link.kind as LinkKind] = link.url;
  return {
    full_name: p.full_name ?? "",
    current_role: p.current_role ?? "",
    location: p.location ?? "",
    headline: p.headline ?? "",
    years: num(p.years_experience),
    target_roles: p.target_roles,
    target_levels: p.target_levels,
    regions: p.regions,
    work_modes: p.work_modes,
    needs_visa: p.needs_visa,
    salary_floor: num(p.salary_floor_lpa),
    salary_target: num(p.salary_target_lpa),
    links,
  };
}

const same = (a: string[], b: string[]) => a.length === b.length && a.every((v, i) => v === b[i]);

/**
 * Only the fields you edited that now differ from what is saved, in the shape the API accepts.
 * `touched` matters: a field you never edited is left alone, so a CV upload that fills in your name
 * is not undone by the empty "name" box still on screen.
 */
export function changes(p: Profile, d: Draft, touched: ReadonlySet<string>): ProfileUpdate {
  const saved = toDraft(p);
  const out: ProfileUpdate = {};
  for (const key of ["full_name", "current_role", "location", "headline"] as const) {
    if (touched.has(key) && d[key].trim() !== saved[key]) out[key] = d[key].trim() || null;
  }
  if (touched.has("years") && d.years.trim() !== saved.years) out.years_experience = d.years.trim() === "" ? null : Number(d.years);
  if (touched.has("target_roles") && !same(d.target_roles, saved.target_roles)) out.target_roles = d.target_roles;
  if (touched.has("target_levels") && !same(d.target_levels, saved.target_levels)) out.target_levels = d.target_levels as ProfileUpdate["target_levels"];
  if (touched.has("regions") && !same(d.regions, saved.regions)) out.regions = d.regions as ProfileUpdate["regions"];
  if (touched.has("work_modes") && !same(d.work_modes, saved.work_modes)) out.work_modes = d.work_modes as ProfileUpdate["work_modes"];
  if (touched.has("needs_visa") && d.needs_visa !== saved.needs_visa) out.needs_visa = d.needs_visa;
  if (touched.has("salary_floor") && d.salary_floor.trim() !== saved.salary_floor) out.salary_floor_lpa = d.salary_floor.trim() === "" ? null : d.salary_floor.trim();
  if (touched.has("salary_target") && d.salary_target.trim() !== saved.salary_target) out.salary_target_lpa = d.salary_target.trim() === "" ? null : d.salary_target.trim();
  if (touched.has("links") && LINK_KINDS.some((k) => d.links[k.kind].trim() !== saved.links[k.kind])) {
    out.links = LINK_KINDS.filter((k) => d.links[k.kind].trim() !== "").map(
      (k): ProfileLink => ({ kind: k.kind, url: d.links[k.kind].trim() }),
    );
  }
  return out;
}

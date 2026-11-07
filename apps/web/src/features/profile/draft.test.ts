import { describe, expect, it } from "vitest";

import { changes, toDraft } from "./draft";
import type { Profile } from "./hooks";

const base: Profile = {
  has_cv: false,
  skills: [],
  role_titles: [],
  years_experience: null,
  updated_at: null,
  full_name: "Priya Sharma",
  headline: null,
  current_role: null,
  location: null,
  target_roles: ["Python Developer"],
  target_levels: [],
  regions: ["India"],
  work_modes: [],
  needs_visa: false,
  salary_floor_lpa: null,
  salary_target_lpa: 30.5,
  links: [{ kind: "github", url: "https://github.com/priya" }],
  cv: { has_cv: false, source: null, filename: null, chars: null },
  setup: { complete: false, completed_at: null, missing: [] },
};

describe("toDraft", () => {
  it("turns numbers into text and links into one box per site", () => {
    const d = toDraft(base);
    expect(d.salary_target).toBe("30.5");
    expect(d.salary_floor).toBe("");
    expect(d.links.github).toBe("https://github.com/priya");
    expect(d.links.leetcode).toBe("");
  });
});

describe("changes", () => {
  it("is empty when nothing was touched, even if the boxes differ from the saved profile", () => {
    // A CV upload filled in the name while the name box on screen was still empty.
    const d = { ...toDraft(base), full_name: "" };
    expect(changes(base, d, new Set())).toEqual({});
  });

  it("sends only the fields you edited", () => {
    const d = { ...toDraft(base), current_role: "  Backend Developer ", years: "5" };
    expect(changes(base, d, new Set(["current_role", "years"]))).toEqual({
      current_role: "Backend Developer",
      years_experience: 5,
    });
  });

  it("clears a field when its box is emptied, and ignores an edit that changes nothing", () => {
    const d = { ...toDraft(base), salary_target: "", full_name: "Priya Sharma" };
    expect(changes(base, d, new Set(["salary_target", "full_name"]))).toEqual({ salary_target_lpa: null });
  });

  it("sends lists whole and links without the empty boxes", () => {
    const d = {
      ...toDraft(base),
      regions: ["India", "Remote (Global)"],
      links: { ...toDraft(base).links, github: "", linkedin: "https://www.linkedin.com/in/priya" },
    };
    expect(changes(base, d, new Set(["regions", "links"]))).toEqual({
      regions: ["India", "Remote (Global)"],
      links: [{ kind: "linkedin", url: "https://www.linkedin.com/in/priya" }],
    });
  });
});

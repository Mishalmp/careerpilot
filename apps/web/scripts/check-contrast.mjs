// Fails when a text/background token pair drops below WCAG 2.2 AA in either theme.
// Reads src/styles/tokens.css (the single source of the colours). Run: node scripts/check-contrast.mjs
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../src/styles/tokens.css"), "utf8");

function block(selector) {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no ${selector} block`);
  const open = css.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < css.length; i++) {
    if (css[i] === "{") depth++;
    if (css[i] === "}" && --depth === 0) return css.slice(open + 1, i);
  }
  throw new Error("unbalanced braces");
}
function vars(text) {
  const out = {};
  for (const m of text.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}
const light = vars(block(":root"));
const dark = { ...light, ...vars(block(".dark")) };

function resolve(map, value, depth = 0) {
  const m = value.match(/^var\((--[\w-]+)\)$/);
  if (!m) return value;
  if (depth > 10) throw new Error("var cycle");
  return resolve(map, map[m[1]], depth + 1);
}
function hex(map, name) {
  const v = resolve(map, map[name]);
  if (!/^#[0-9a-f]{6}$/i.test(v)) throw new Error(`${name} is not a hex colour: ${v}`);
  return v;
}
function luminance(h) {
  const c = [1, 3, 5]
    .map((i) => parseInt(h.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (hi + 0.05) / (lo + 0.05);
}

// [foreground token, background token, minimum ratio, what it is]
const PAIRS = [
  ["--foreground", "--background", 4.5, "body text"],
  ["--foreground", "--surface", 4.5, "text on card"],
  ["--muted-foreground", "--background", 4.5, "secondary text"],
  ["--muted-foreground", "--surface", 4.5, "secondary text on card"],
  ["--muted-foreground", "--surface-muted", 4.5, "secondary text on muted surface"],
  ["--muted-foreground", "--surface-hover", 4.5, "secondary text on hover surface"],
  ["--primary-foreground", "--primary", 4.5, "primary button text"],
  ["--primary-foreground", "--primary-hover", 4.5, "primary button text (hover)"],
  ["--accent-text", "--background", 4.5, "link / accent text"],
  ["--accent-text", "--surface", 4.5, "accent text on card"],
  ["--accent-text", "--accent-soft", 4.5, "selected item text"],
  ["--success-text", "--success-soft", 4.5, "success badge"],
  ["--warning-text", "--warning-soft", 4.5, "warning badge"],
  ["--danger-text", "--danger-soft", 4.5, "danger badge"],
  ["--violet-text", "--violet-soft", 4.5, "interview badge"],
  ["--danger-text", "--surface", 4.5, "error text on card"],
  ["--primary-foreground", "--danger-solid", 4.5, "destructive button text"],
  ["--foreground", "--sidebar", 4.5, "sidebar text"],
  ["--muted-foreground", "--sidebar", 4.5, "sidebar secondary text"],
  ["--ring", "--background", 3, "focus ring (non-text 3:1)"],
  ["--ring", "--surface", 3, "focus ring on card"],
  ["--input", "--surface", 3, "input border (non-text 3:1)"],
];

let failed = 0;
for (const [themeName, map] of [["light", light], ["dark", dark]]) {
  for (const [fg, bg, min, what] of PAIRS) {
    const r = ratio(hex(map, fg), hex(map, bg));
    const ok = r >= min;
    if (!ok) failed++;
    console.log(`${ok ? "ok  " : "FAIL"} ${themeName.padEnd(5)} ${r.toFixed(2).padStart(5)} (min ${min}) ${what}  [${fg} on ${bg}]`);
  }
}
if (failed) {
  console.error(`\n${failed} pair(s) below the minimum`);
  process.exit(1);
}
console.log("\nall pairs pass");

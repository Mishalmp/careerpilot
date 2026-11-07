import { cn } from "@/lib/utils";

function initials(name: string): string {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join("");
  return letters || "?";
}

/** The person's initials on a blue disc. Decorative: the name is always written next to it. */
export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-flex size-9 shrink-0 items-center justify-center rounded-full text-[0.8125rem] font-semibold text-white", className)}
      style={{ background: "linear-gradient(135deg, var(--blue-9), var(--blue-11))" }}
    >
      {initials(name)}
    </span>
  );
}

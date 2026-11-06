"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/prep", label: "Roadmap" },
  { href: "/prep/topics", label: "Topics" },
  { href: "/prep/guides", label: "Guides" },
];

export function PrepNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Prep sections" className="flex gap-1 border-b border-border-subtle">
      {TABS.map((tab) => {
        const active = tab.href === "/prep" ? pathname === "/prep" : pathname.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={`px-3 py-2 text-sm ${active ? "border-b-2 border-foreground font-medium" : "text-muted-foreground "}`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}

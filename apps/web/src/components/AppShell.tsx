"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { button, muted } from "@/components/ui";
import { useLogout, useSession } from "@/lib/session";

const NAV = [
  { href: "/", label: "Today" },
  { href: "/jobs", label: "Jobs" },
  { href: "/discover", label: "Discover" },
  { href: "/prep", label: "Prep" },
  { href: "/practice", label: "Practice" },
  { href: "/ask", label: "Ask" },
  { href: "/mock", label: "Mock" },
  { href: "/tasks", label: "Tasks" },
  { href: "/insights", label: "Insights" },
  { href: "/offers", label: "Offers" },
  { href: "/stories", label: "Stories" },
];

/** Signed-in frame: redirects to /login without a session and shows the main navigation. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const session = useSession();
  const logout = useLogout();

  useEffect(() => {
    if (session.isSuccess && session.data === null) router.replace("/login");
  }, [session.isSuccess, session.data, router]);

  if (session.isError) {
    return (
      <main className="flex flex-1 items-center justify-center p-6">
        <p role="alert">The API is not reachable. Start it and reload.</p>
      </main>
    );
  }
  // Children render only once the session (and its CSRF token) is known.
  if (!session.data) return <main className="flex-1 p-6" aria-busy="true" />;

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex flex-wrap items-center gap-6 border-b border-black/10 px-6 py-3 dark:border-white/15">
        <span className="font-semibold">CareerPilot</span>
        <nav aria-label="Main" className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={active ? "font-semibold underline underline-offset-4" : "hover:underline"}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm">
          <span className={muted}>{session.data.user.email}</span>
          <button type="button" onClick={() => logout.mutate()} className={button}>
            Sign out
          </button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 p-6">{children}</main>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useLogout, useSession } from "@/lib/session";

export default function Home() {
  const router = useRouter();
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
  if (!session.data) {
    return <main className="flex-1 p-6" aria-busy="true" />;
  }

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-black/10 px-6 py-3 dark:border-white/15">
        <span className="font-semibold">CareerPilot</span>
        <div className="flex items-center gap-4 text-sm">
          <span>{session.data.user.email}</span>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="rounded border border-black/20 px-3 py-1 dark:border-white/25"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 p-6">
        <h1 className="text-2xl font-semibold">Today</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Foundation is running. The job tracker and the prep roadmap arrive in Phase 1.
        </p>
      </main>
    </div>
  );
}

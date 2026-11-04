"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useLogin, useSession } from "@/lib/session";

export default function LoginPage() {
  const router = useRouter();
  const session = useSession();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (session.data) router.replace("/");
  }, [session.data, router]);

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          login.mutate({ email, password });
        }}
        className="w-full max-w-sm space-y-4 rounded-lg border border-black/10 p-6 dark:border-white/15"
      >
        <h1 className="text-xl font-semibold">Sign in to CareerPilot</h1>

        <label className="block space-y-1 text-sm">
          <span>Email</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded border border-black/20 bg-transparent px-3 py-2 dark:border-white/25"
          />
        </label>

        <label className="block space-y-1 text-sm">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded border border-black/20 bg-transparent px-3 py-2 dark:border-white/25"
          />
        </label>

        <p role="alert" className="min-h-5 text-sm text-red-600 dark:text-red-400">
          {login.error?.message}
        </p>

        <button
          type="submit"
          disabled={login.isPending}
          className="w-full rounded bg-foreground px-3 py-2 text-sm font-medium text-background disabled:opacity-60"
        >
          {login.isPending ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </main>
  );
}

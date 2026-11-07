"use client";

import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";

/** Shown when a page crashes while drawing. The crash is logged to the console; nothing is hidden by a blank screen. */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Page crashed:", error);
  }, [error]);
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 p-6">
      <ErrorState
        title="This page crashed"
        description="Nothing you saved is lost. Try again, and if it keeps happening, reload the page or tell whoever runs this app."
        onRetry={reset}
      />
      <Button asChild variant="ghost">
        <Link href="/">Go to Today</Link>
      </Button>
    </main>
  );
}

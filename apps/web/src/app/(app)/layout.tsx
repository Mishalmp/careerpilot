import { Suspense } from "react";

import { AppShell } from "@/components/AppShell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // The shell reads the current path, which Next only knows at request time.
  return (
    <Suspense fallback={null}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}

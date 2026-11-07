import { Compass } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center p-6">
      <EmptyState
        icon={<Compass aria-hidden="true" />}
        title="That page does not exist"
        description="The link may be old, or mistyped."
        action={
          <Button asChild variant="primary">
            <Link href="/">Go to Today</Link>
          </Button>
        }
      />
    </main>
  );
}

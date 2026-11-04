import type { Status } from "@/lib/api/types";

import { statusTone } from "./status";

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${statusTone(status)}`}>
      {status}
    </span>
  );
}

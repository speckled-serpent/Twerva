import type { ReactElement } from "react";

import { useCanWriteOps } from "../session/OpsSessionContext";

/**
 * Subtle banner when the signed-in operator is a reader.
 *
 * @returns A read-only notice, or null for admins
 */
export function ReadOnlyNotice(): ReactElement | null {

  const canWrite: boolean = useCanWriteOps();

  if (canWrite) {
    return null;
  }

  return (
    <p className="readonly-banner" role="status">
      Read-only role: generate, approve, schedule, and other writes are disabled.
    </p>
  );
}

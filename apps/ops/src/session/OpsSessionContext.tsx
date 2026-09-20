import { createContext, useContext } from "react";

import type { OpsUserReadResponse, OpsUserRole } from "../api/types";

export interface OpsSessionContextValue {
  currentOperator: OpsUserReadResponse;
  canWrite: boolean;
}

export const OpsSessionContext = createContext<OpsSessionContextValue | null>(null);

/**
 * Return the signed-in operator and whether writes are allowed.
 *
 * @returns Session context for the current ops operator
 */
export function useOpsSession(): OpsSessionContextValue {

  const sessionContext: OpsSessionContextValue | null = useContext(OpsSessionContext);

  if (sessionContext === null) {
    throw new Error("useOpsSession must be used inside OpsSessionContext.Provider.");
  }

  return sessionContext;
}

/**
 * Return true when the signed-in operator may mutate `/api/v1`.
 *
 * @returns Whether write actions should be enabled
 */
export function useCanWriteOps(): boolean {

  const sessionContext: OpsSessionContextValue = useOpsSession();

  return sessionContext.canWrite;
}

/**
 * Return true when the signed-in operator is an admin.
 *
 * @param role - Operator role from `/auth/me`
 * @returns Whether the role is admin
 */
export function isAdminOpsRole(role: OpsUserRole): boolean {

  return role === "admin";
}

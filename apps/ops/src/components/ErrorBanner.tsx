import type { ReactElement } from "react";

import { ApiClientError } from "../api/client";

export interface ErrorBannerProps {
  error: unknown;
}

/**
 * Render an API or unexpected error as plain text.
 *
 * @param props - Banner props
 * @returns An error paragraph, or null when there is no error
 */
export function ErrorBanner({ error }: ErrorBannerProps): ReactElement | null {

  if (error === null || error === undefined) {
    return null;
  }

  const errorText: string = formatUnknownError(error);

  return (
    <p className="error-banner" role="alert">
      {errorText}
    </p>
  );
}

function formatUnknownError(error: unknown): string {

  if (error instanceof ApiClientError) {
    return error.detailText;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return String(error);
}

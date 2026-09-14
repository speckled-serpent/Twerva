import type { ReactElement } from "react";

/**
 * Minimal ops console landing page.
 *
 * @returns A React element for the empty Twerva ops shell
 */
export function App(): ReactElement {

  const headingText: string = "Twerva ops console stub";
  const supportingText: string =
    "Empty shell. The source → generate → approve → publish loop is not wired yet.";

  return (
    <main className="ops-console-shell">
      <h1>{headingText}</h1>
      <p>{supportingText}</p>
    </main>
  );
}

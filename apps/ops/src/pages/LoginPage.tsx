import { useState, type ChangeEvent, type FormEvent, type ReactElement } from "react";

import { loginOpsOperator } from "../api/client";
import type { OpsUserReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";

export interface LoginPageProps {
  onSignedIn: (opsUser: OpsUserReadResponse) => void;
}

/**
 * Operator login form. Shown when `GET /api/v1/auth/me` is 401.
 *
 * @param props - Success callback after the session cookie is set
 * @returns The login page
 */
export function LoginPage({ onSignedIn }: LoginPageProps): ReactElement {

  const [username, setUsername] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [loginError, setLoginError] = useState<unknown>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleSubmit = async (formEvent: FormEvent<HTMLFormElement>): Promise<void> => {

    formEvent.preventDefault();
    setLoginError(null);
    setIsSubmitting(true);

    try {
      const signedInOperator: OpsUserReadResponse = await loginOpsOperator({
        username,
        password,
      });

      onSignedIn(signedInOperator);
    } catch (caughtError: unknown) {
      setLoginError(caughtError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="ops-login-shell">
      <main className="ops-login-card">
        <div className="ops-brand-block">
          <strong className="ops-brand">Twerva</strong>
          <span className="ops-brand-sub">ops</span>
        </div>
        <h1>Sign in</h1>
        <p className="lede">
          Operator login for the Twerva console. Session cookie is httpOnly.
        </p>
        <ErrorBanner error={loginError} />
        <form className="stack-form" onSubmit={(formEvent: FormEvent<HTMLFormElement>): void => {
          void handleSubmit(formEvent);
        }}>
          <label>
            Username
            <input
              type="text"
              name="username"
              autoComplete="username"
              value={username}
              onChange={(changeEvent: ChangeEvent<HTMLInputElement>): void => {
                setUsername(changeEvent.target.value);
              }}
              required={true}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(changeEvent: ChangeEvent<HTMLInputElement>): void => {
                setPassword(changeEvent.target.value);
              }}
              required={true}
            />
          </label>
          <div className="button-row">
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Signing in…" : "Sign in"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

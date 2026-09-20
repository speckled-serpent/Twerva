import { useState, type FormEvent, type ReactElement } from "react";

import { changeOwnOpsPassword } from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { useOpsSession } from "../session/OpsSessionContext";

/**
 * Account settings: change the signed-in operator's password.
 *
 * @returns The Account page
 */
export function AccountPage(): ReactElement {

  const { currentOperator } = useOpsSession();
  const [currentPassword, setCurrentPassword] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [formError, setFormError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleChangePassword = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setFormError(null);
    setStatusMessage("");

    if (newPassword !== confirmPassword) {
      setFormError(new Error("New password and confirmation do not match."));

      return;
    }

    setIsSubmitting(true);

    try {
      await changeOwnOpsPassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setStatusMessage("Password changed. Use the new password next time you sign in.");
    } catch (caughtError: unknown) {
      setFormError(caughtError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section>
      <h1>Account</h1>
      <p className="lede">
        Signed in as <strong>{currentOperator.username}</strong> ({currentOperator.role}).
        Change your own password here — bootstrap env does not rotate an existing admin.
      </p>
      <ErrorBanner error={formError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      <h2>Change password</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        void handleChangePassword(formEvent);
      }}>
        <label>
          Current password
          <input
            type="password"
            name="current-password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(changeEvent): void => {
              setCurrentPassword(changeEvent.target.value);
            }}
            required={true}
          />
        </label>
        <label>
          New password
          <input
            type="password"
            name="new-password"
            autoComplete="new-password"
            minLength={8}
            value={newPassword}
            onChange={(changeEvent): void => {
              setNewPassword(changeEvent.target.value);
            }}
            required={true}
          />
        </label>
        <label>
          Confirm new password
          <input
            type="password"
            name="confirm-password"
            autoComplete="new-password"
            minLength={8}
            value={confirmPassword}
            onChange={(changeEvent): void => {
              setConfirmPassword(changeEvent.target.value);
            }}
            required={true}
          />
        </label>
        <div className="button-row">
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "Change password"}
          </button>
        </div>
      </form>
    </section>
  );
}

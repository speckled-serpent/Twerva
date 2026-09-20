import { useEffect, useState, type FormEvent, type ReactElement } from "react";

import {
  createOpsUser,
  listOpsUsers,
  patchOpsUserRole,
  resetOpsUserPassword,
} from "../api/client";
import type { OpsUserReadResponse, OpsUserRole } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";

/**
 * Admin-only ops user list and create form.
 *
 * @returns The Users page
 */
export function UsersPage(): ReactElement {

  const [opsUsers, setOpsUsers] = useState<OpsUserReadResponse[]>([]);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isBusy, setIsBusy] = useState<boolean>(false);

  const [newUsername, setNewUsername] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [newRole, setNewRole] = useState<OpsUserRole>("reader");
  const [resetPasswordByUserId, setResetPasswordByUserId] = useState<Record<string, string>>(
    {},
  );

  const reloadUsers = async (): Promise<void> => {

    const loadedOpsUsers: OpsUserReadResponse[] = await listOpsUsers();

    setOpsUsers(loadedOpsUsers);
  };

  useEffect((): (() => void) => {
    let isCancelled: boolean = false;

    const loadPage = async (): Promise<void> => {

      try {
        const loadedOpsUsers: OpsUserReadResponse[] = await listOpsUsers();

        if (isCancelled) {
          return;
        }

        setOpsUsers(loadedOpsUsers);
        setLoadError(null);
      } catch (caughtError: unknown) {
        if (isCancelled) {
          return;
        }

        setLoadError(caughtError);
      }
    };

    void loadPage();

    return (): void => {
      isCancelled = true;
    };
  }, []);

  const handleCreateUser = async (formEvent: FormEvent): Promise<void> => {

    formEvent.preventDefault();
    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      const createdOpsUser: OpsUserReadResponse = await createOpsUser({
        username: newUsername,
        password: newPassword,
        role: newRole,
      });

      setNewUsername("");
      setNewPassword("");
      setNewRole("reader");
      setStatusMessage(`Created ${createdOpsUser.username} (${createdOpsUser.role}).`);
      await reloadUsers();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const handleRoleChange = async (
    opsUserId: string,
    nextRole: OpsUserRole,
  ): Promise<void> => {

    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      const updatedOpsUser: OpsUserReadResponse = await patchOpsUserRole(opsUserId, {
        role: nextRole,
      });

      setStatusMessage(`Updated ${updatedOpsUser.username} to ${updatedOpsUser.role}.`);
      await reloadUsers();
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  const handleResetPassword = async (opsUserId: string): Promise<void> => {

    const nextPassword: string = resetPasswordByUserId[opsUserId] ?? "";

    if (nextPassword.length < 8) {
      setActionError(new Error("Reset password must be at least 8 characters."));

      return;
    }

    setIsBusy(true);
    setActionError(null);
    setStatusMessage("");

    try {
      await resetOpsUserPassword(opsUserId, { new_password: nextPassword });
      setResetPasswordByUserId((previousPasswords: Record<string, string>): Record<string, string> => {
        return {
          ...previousPasswords,
          [opsUserId]: "",
        };
      });
      setStatusMessage("Password reset. It is not shown again.");
    } catch (caughtError: unknown) {
      setActionError(caughtError);
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <section>
      <h1>Users</h1>
      <p className="lede">
        Admin-only. Create operators and assign <code>admin</code> (full) or{" "}
        <code>reader</code> (GET-only). Passwords are never listed.
      </p>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError} />
      {statusMessage !== "" ? <p className="status-banner">{statusMessage}</p> : null}

      <h2>Create user</h2>
      <form className="stack-form" onSubmit={(formEvent: FormEvent): void => {
        void handleCreateUser(formEvent);
      }}>
        <label>
          Username
          <input
            type="text"
            name="new-username"
            autoComplete="off"
            value={newUsername}
            onChange={(changeEvent): void => {
              setNewUsername(changeEvent.target.value);
            }}
            required={true}
          />
        </label>
        <label>
          Password
          <input
            type="password"
            name="new-user-password"
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
          Role
          <select
            value={newRole}
            onChange={(changeEvent): void => {
              setNewRole(changeEvent.target.value as OpsUserRole);
            }}
          >
            <option value="reader">reader</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <button type="submit" disabled={isBusy}>
          Create user
        </button>
      </form>

      <h2>Operators</h2>
      {loadError !== null ? null : opsUsers.length === 0 ? (
        <p>No operators returned.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th>Created</th>
              <th>Reset password</th>
            </tr>
          </thead>
          <tbody>
            {opsUsers.map((opsUser: OpsUserReadResponse): ReactElement => (
              <tr key={opsUser.id}>
                <td>{opsUser.username}</td>
                <td>
                  <select
                    value={opsUser.role}
                    disabled={isBusy}
                    onChange={(changeEvent): void => {
                      void handleRoleChange(
                        opsUser.id,
                        changeEvent.target.value as OpsUserRole,
                      );
                    }}
                  >
                    <option value="admin">admin</option>
                    <option value="reader">reader</option>
                  </select>
                </td>
                <td>{opsUser.created_at}</td>
                <td>
                  <div className="button-row">
                    <input
                      type="password"
                      autoComplete="new-password"
                      minLength={8}
                      placeholder="new password"
                      value={resetPasswordByUserId[opsUser.id] ?? ""}
                      onChange={(changeEvent): void => {
                        const nextPassword: string = changeEvent.target.value;

                        setResetPasswordByUserId((
                          previousPasswords: Record<string, string>,
                        ): Record<string, string> => {
                          return {
                            ...previousPasswords,
                            [opsUser.id]: nextPassword,
                          };
                        });
                      }}
                    />
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={(): void => {
                        void handleResetPassword(opsUser.id);
                      }}
                    >
                      Reset
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

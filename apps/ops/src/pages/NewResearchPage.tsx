import { useState, type FormEvent, type ReactElement } from "react";

import { createResearch } from "../api/client";
import type { ResearchReadResponse } from "../api/types";
import { ErrorBanner } from "../components/ErrorBanner";
import { ReadOnlyNotice } from "../components/ReadOnlyNotice";
import { useCanWriteOps } from "../session/OpsSessionContext";

export const CREATE_RESEARCH_TITLE_ERROR: string = "Title is required.";

export interface NewResearchPageProps {
  onCreated: (createdResearch: ResearchReadResponse) => void;
  onCancel: () => void;
}

/**
 * Create Research: a title, then open the document so the body can be written.
 *
 * @param props - Success and cancel navigation callbacks
 * @returns The create-research form
 */
export function NewResearchPage({ onCreated, onCancel }: NewResearchPageProps): ReactElement {

  const canWrite: boolean = useCanWriteOps();
  const [researchTitle, setResearchTitle] = useState<string>("");
  const [saveError, setSaveError] = useState<unknown>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  const handleCreate = async (submitEvent: FormEvent<HTMLFormElement>): Promise<void> => {
    submitEvent.preventDefault();

    if (!canWrite || isSaving) {
      return;
    }

    if (researchTitle.trim() === "") {
      setSaveError(new Error(CREATE_RESEARCH_TITLE_ERROR));

      return;
    }

    setIsSaving(true);
    setSaveError(null);

    try {
      const createdResearch: ResearchReadResponse = await createResearch({
        title: researchTitle.trim(),
      });

      onCreated(createdResearch);
    } catch (caughtError: unknown) {
      setSaveError(caughtError);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <section>
      <div className="page-header-row">
        <div>
          <h1>Create Research</h1>
          <p className="lede">
            A research item is one text document. After this, it opens so you can write it.
          </p>
        </div>
        <button type="button" onClick={onCancel}>
          Back to Research
        </button>
      </div>
      <ReadOnlyNotice />
      {canWrite ? (
        <form
          id="create-research-form"
          className="stack-form"
          onSubmit={(submitEvent: FormEvent<HTMLFormElement>): void => {
            void handleCreate(submitEvent);
          }}
        >
          <label>
            Title
            <input
              id="create-research-title"
              value={researchTitle}
              onChange={(changeEvent): void => {
                setResearchTitle(changeEvent.target.value);
              }}
            />
          </label>
          <ErrorBanner error={saveError} />
          <div className="button-row">
            <button id="create-research-submit" type="submit" className="primary" disabled={isSaving}>
              {isSaving ? "Creating…" : "Create Research"}
            </button>
            <button type="button" onClick={onCancel} disabled={isSaving}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <p>Creating research is an admin action.</p>
      )}
    </section>
  );
}

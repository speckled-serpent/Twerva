import type { ReactElement } from "react";

import type {
  CarouselInstructionReadResponse,
  CarouselReadResponse,
} from "../api/types";
import {
  INSTRUCTION_SAMPLE_TEMPLATE,
  orderedInstructionDocuments,
} from "./instructionTemplate";

export interface CarouselInstructionsStepProps {
  carousel: CarouselReadResponse;
}

/**
 * Step 1: the carousel's instruction documents, as read-only source.
 *
 * Documents are shown in position order. Zero documents shows a sample
 * that is not saved. There is no textarea and no Generate button. This
 * step does not write a row.
 *
 * @param props - The open carousel
 * @returns The Instructions step
 */
export function CarouselInstructionsStep({
  carousel,
}: CarouselInstructionsStepProps): ReactElement {

  const documents: CarouselInstructionReadResponse[] = orderedInstructionDocuments(
    carousel.instructions,
  );

  return (
    <section
      id="carousel-instructions"
      className="stack-form"
      aria-label="Instructions"
    >
      {documents.length === 0 ? (
        <>
          <p>No instructions yet.</p>
          <p className="field-hint">Sample. Not saved.</p>
          <pre className="instruction-source">{INSTRUCTION_SAMPLE_TEMPLATE}</pre>
        </>
      ) : (
        <ol className="instruction-documents">
          {documents.map((document: CarouselInstructionReadResponse): ReactElement => (
            <li key={document.id}>
              <pre className="instruction-source">{document.body}</pre>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export type CreateSourceKind = "album" | "resource";

export const CREATE_SOURCE_NAME_ERROR: string = "Enter a name.";
export const CREATE_SOURCE_PROVENANCE_ERROR: string = "A resource needs a provenance note.";
export const CREATE_SOURCE_FILE_ERROR: string = "Choose a Markdown (.md) or plain text (.txt) file.";
export const CREATE_SOURCE_TYPE_ERROR: string = "Resource files must be Markdown (.md) or plain text (.txt).";

/**
 * Client check before creating a source. The server repeats the file rules.
 *
 * @param kind - Album or resource
 * @param name - Name field
 * @param provenance - Provenance note, ignored for an album
 * @param fileName - Chosen file name, or null when no file is chosen
 * @returns An inline error, or null when the form can be submitted
 */
export function createSourceFieldError(
  kind: CreateSourceKind,
  name: string,
  provenance: string,
  fileName: string | null,
): string | null {

  if (name.trim() === "") {
    return CREATE_SOURCE_NAME_ERROR;
  }

  if (kind === "album") {
    return null;
  }

  if (provenance.trim() === "") {
    return CREATE_SOURCE_PROVENANCE_ERROR;
  }

  if (fileName === null || fileName.trim() === "") {
    return CREATE_SOURCE_FILE_ERROR;
  }

  const loweredName: string = fileName.trim().toLowerCase();

  if (!loweredName.endsWith(".md") && !loweredName.endsWith(".txt")) {
    return CREATE_SOURCE_TYPE_ERROR;
  }

  return null;
}

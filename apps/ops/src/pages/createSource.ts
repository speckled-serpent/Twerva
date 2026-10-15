export const CREATE_SOURCE_NAME_ERROR: string = "Name is required.";
export const CREATE_SOURCE_THEME_ERROR: string = "A source needs a theme.";

/**
 * Validate the create-source form. Name and theme are both required.
 *
 * @param sourceName - Name field
 * @param themeId - Selected theme id
 * @returns An error message, or null when the fields are ready to submit
 */
export function createSourceFieldError(sourceName: string, themeId: string): string | null {

  if (sourceName.trim() === "") {
    return CREATE_SOURCE_NAME_ERROR;
  }

  if (themeId.trim() === "") {
    return CREATE_SOURCE_THEME_ERROR;
  }

  return null;
}

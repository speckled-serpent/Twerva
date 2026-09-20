import type { ChangeEvent, ReactElement } from "react";

import type { CarouselTemplateReadResponse } from "../api/types";

export interface TemplatePickerProps {
  templates: CarouselTemplateReadResponse[];
  selectedTemplateId: string;
  disabled: boolean;
  onChange: (templateId: string) => void;
}

/**
 * Restricted Spotmu template select for generate / regenerate.
 *
 * @param props - Registry, current id, write flag, change handler
 * @returns A labeled select
 */
export function TemplatePicker({
  templates,
  selectedTemplateId,
  disabled,
  onChange,
}: TemplatePickerProps): ReactElement {

  return (
    <label>
      Template
      <select
        value={selectedTemplateId}
        disabled={disabled}
        onChange={(changeEvent: ChangeEvent<HTMLSelectElement>): void => {
          onChange(changeEvent.target.value);
        }}
      >
        {templates.map((carouselTemplate: CarouselTemplateReadResponse): ReactElement => (
          <option key={carouselTemplate.template_id} value={carouselTemplate.template_id}>
            {carouselTemplate.name}
            {carouselTemplate.is_default ? " (default)" : ""}
          </option>
        ))}
      </select>
      {renderSelectedTemplateDescription(templates, selectedTemplateId)}
    </label>
  );
}

function renderSelectedTemplateDescription(
  templates: CarouselTemplateReadResponse[],
  selectedTemplateId: string,
): ReactElement | null {

  const selectedTemplate: CarouselTemplateReadResponse | undefined = templates.find(
    (carouselTemplate: CarouselTemplateReadResponse): boolean => {
      return carouselTemplate.template_id === selectedTemplateId;
    },
  );

  if (selectedTemplate === undefined) {
    return null;
  }

  return <span className="template-picker-description">{selectedTemplate.description}</span>;
}

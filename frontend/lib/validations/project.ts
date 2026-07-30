// Validation for the create-project form. Name is required; everything else is
// optional but length-bounded where the backend enforces limits.

export interface ProjectFormValues {
  name: string;
  description?: string;
  book_title: string;
  subtitle?: string;
  author_name?: string;
  language?: string;
  target_audience?: string;
  writing_style?: string;
}

export interface ProjectFormErrors {
  name?: string;
  book_title?: string;
  description?: string;
}

export function validateProjectForm(values: ProjectFormValues): ProjectFormErrors {
  const errors: ProjectFormErrors = {};
  if (!values.name?.trim()) {
    errors.name = "Project name is required.";
  } else if (values.name.trim().length > 220) {
    errors.name = "Project name is too long.";
  }
  if (!values.book_title?.trim()) {
    errors.book_title = "Book title is required.";
  } else if (values.book_title.trim().length > 300) {
    errors.book_title = "Book title is too long.";
  }
  if (values.description && values.description.length > 2000) {
    errors.description = "Description is too long.";
  }
  return errors;
}

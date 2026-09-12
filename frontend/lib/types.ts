export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type User = {
  id: string;
  email: string;
  name: string;
  institution: string;
  role: string;
  account_status: string;
};

export type Plan = {
  code: "FREE" | "STUDENT" | "RESEARCHER" | "ORGANIZATION";
  name: string;
  description: string;
  monthly_price_kobo: number;
  yearly_price_kobo: number | null;
  monthly_page_limit: number;
  monthly_bot_lab_runs: number;
  batch_size_limit: number;
  max_team_members: number;
  contact_required: boolean;
  has_xlsx: boolean;
  has_google_forms: boolean;
  has_advanced_exports: boolean;
  has_analytics: boolean;
  priority_processing: boolean;
  features: string[];
};

export type BillingSummary = {
  plan: Plan;
  subscription: null | {
    status: string;
    billing_cycle: "MONTHLY" | "YEARLY";
    current_period_end: string;
    cancel_at_period_end: boolean;
  };
  usage: {
    month: string;
    pages_used: number;
    included_pages: number;
    extra_pages: number;
    pages_remaining: number;
    bot_lab_runs_used: number;
    bot_lab_runs_included: number;
  };
  is_organization_member: boolean;
  paystack_configured: boolean;
  admin_contact_email: string;
};

export type PaymentTransaction = {
  id: string;
  product: "SUBSCRIPTION" | "EXTRA_PAGES";
  plan_code: string | null;
  billing_cycle: string;
  reference: string;
  amount_kobo: number;
  currency: string;
  status: string;
  authorization_url: string;
  paid_at: string | null;
  created_at: string;
};

export type Option = { id: string; key: string; label: string; value: string; position: number };

export type Question = {
  id: string;
  key: string;
  position: number;
  text: string;
  type: string;
  required: boolean;
  template_page_number: number | null;
  options: Option[];
};

export type TemplatePage = {
  id: string;
  page_number: number;
  reference_text: string;
  anchors: string[];
  text_signature: string;
};

export type Version = {
  id: string;
  version_number: number;
  parse_status: string;
  expected_page_count: number;
  template_pages: TemplatePage[];
  questions: Question[];
};

export type Questionnaire = {
  id: string;
  title: string;
  description: string;
  status: string;
  latest_version: Version | null;
  created_at: string;
};

export type BotRun = {
  id: string;
  questionnaire_version: string;
  questionnaire_title: string;
  requested_responses: number;
  generated_responses: number;
  status: string;
  error_message: string;
  download_url: string | null;
  created_at: string;
};

export type AppsScriptQuestion = {
  key: string;
  text: string;
  type: string;
  suggested_google_item_title: string;
};

export type AppsScriptPreview = {
  title: string;
  source_type: "RESPONSE_BATCH" | "BOT_RUN";
  data_classification: string;
  response_count: number;
  physical_page_count: number;
  expected_page_count: number;
  questions: AppsScriptQuestion[];
};

export type AppsScriptJob = {
  id: string;
  source_type: "RESPONSE_BATCH" | "BOT_RUN";
  source_name: string;
  form_id: string;
  mappings: Record<string, string>;
  script: string;
  response_count: number;
  data_classification: string;
  download_url: string;
  created_at: string;
};

export type Batch = {
  id: string;
  questionnaire_version: string;
  questionnaire_title: string;
  name: string;
  status: string;
  response_count: number;
  created_at: string;
};

export type OCRJob = {
  id: string;
  status: string;
  engine: string;
  error_message: string;
  extraction?: { structured_output: Record<string, unknown>; warnings: string[] };
};

export type Document = {
  id: string;
  original_filename: string;
  document_type: string;
  grouping_mode: string;
  page_count: number;
  status: string;
  response: string | null;
  download_url: string;
  ocr_job: OCRJob;
  pages: ResponsePage[];
  created_at: string;
};

export type ValidationIssue = {
  code: string;
  message: string;
  severity: "ERROR" | "WARNING";
  pages?: number[];
};

export type ResponsePage = {
  id: string;
  response: string;
  document_id: string;
  original_filename: string;
  content_type: string;
  source_page_number: number;
  original_upload_order: number;
  detected_template_page_number: number | null;
  assigned_template_page_number: number | null;
  classification_confidence: string | null;
  classification_method: string;
  processing_status: string;
  validation_issues: ValidationIssue[];
  file_url: string;
  ocr_text: string;
};

export type Answer = {
  id: string;
  question_text: string;
  question_type: string;
  options: Option[];
  value_text: string;
  value_json: unknown;
  confidence: string | null;
  review_status: string;
};

export type QuestionnaireResponse = {
  id: string;
  batch: string;
  questionnaire_title: string;
  respondent_reference: string;
  sequence: number | null;
  status: string;
  expected_page_count: number;
  uploaded_page_count: number;
  validation_issues: ValidationIssue[];
  pages: ResponsePage[];
  answers: Answer[];
  source_document_id: string | null;
};

export type BulkPreparation = {
  expected_page_count: number;
  response_count: number;
  assignments: Array<{
    upload_index: number;
    response_id: string;
    respondent_reference: string;
    original_upload_order: number;
    template_page_number: number;
  }>;
};

export type Order = {
  reference: string;
  title: string;
  service_type: "DIGITIZATION" | "SYNTHETIC_DATA";
  status: string;
  respondent_count: number;
  pages_per_respondent: number;
  question_count: number;
  expected_page_count: number;
  synthetic_response_count: number;
  google_form_url: string;
  google_form_id: string;
  amount_ngn: string;
  payment_status: string;
  payment_rejection_reason: string;
  payment_sender_name: string;
  payment_reference: string;
  payment_claimed_at: string | null;
  payment_verified_at: string | null;
  created_at: string;
  instructions: string;
  classification: string;
  result_available: boolean;
  payment_available: boolean;
  processing_mode: string;
  bank: {
    bank_name: string;
    account_name: string;
    account_number: string;
  } | null;
  uploads_summary: {
    expected_pages: number;
    uploaded_pages: number;
    template_pages: number;
    expected_respondents: number;
    duplicate_files: boolean;
    incomplete_respondents: number[];
    complete: boolean;
  };
};
export type Upload = {
  id: string;
  upload_key: string;
  filename: string;
  page_count: number;
  kind: string;
  status: string;
  respondent_sequence: number | null;
};
export type Respondent = {
  id: string;
  sequence: number;
  reference: string;
  status: string;
  expected_pages: number;
  uploaded_pages: number;
  missing_pages: number[];
  failed_pages: number;
  issues: { message: string }[];
};
export type Configuration = {
  digitization_rate_ngn: string;
  synthetic_rate_ngn: string;
  max_respondents: number;
  max_pages: number;
  max_synthetic_responses: number;
  payment_available: boolean;
  test_deployment: boolean;
  processing_mode: string;
};
export const money = (amount: string | number) =>
  new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(
    Number(amount),
  );
export const words = (value: string) => value.replaceAll("_", " ");

/**
 * The API contract, mirrored from the backend's Pydantic response models.
 *
 * Every enum is a union of string literals rather than `string`, so an
 * unhandled documentation status is a compile error instead of a blank badge.
 *
 * This file is maintained by hand against `backend/src/api/schemas/`. The
 * honest next step at any larger scale is generating it from the OpenAPI
 * schema FastAPI already emits; the trade is recorded in the README.
 */

export type DocumentationStatus =
  | 'well_documented'
  | 'ambiguous'
  | 'mentioned_without_plan';

export type GapSeverity = 'low' | 'medium' | 'high';

export type AnalysisStatus = 'succeeded' | 'invalid_output' | 'provider_error';

export type ProviderName = 'mock' | 'gemini';

export type QuoteVerificationStatus = 'exact' | 'normalized' | 'fuzzy' | 'not_found';

export type ReviewStatus = 'pending' | 'reviewed';

export type ConditionOrigin = 'ai' | 'human';

export type ReviewAction = 'accepted' | 'edited' | 'rejected' | 'added';

export interface UserResponse {
  readonly uid: string;
  readonly email: string;
  readonly display_name: string | null;
  readonly created_at: string;
}

export interface NoteResponse {
  readonly note_id: string;
  readonly content: string;
  readonly pseudonym: string | null;
  readonly visit_date: string | null;
  readonly word_count: number;
  readonly created_at: string;
  readonly updated_at: string;
  readonly latest_analysis_id: string | null;
  readonly latest_review_id: string | null;
  readonly review_status: ReviewStatus;
  readonly condition_count: number;
  readonly analysis_count: number;
}

export interface NoteSummaryResponse {
  readonly note_id: string;
  readonly pseudonym: string | null;
  readonly visit_date: string | null;
  readonly created_at: string;
  readonly word_count: number;
  readonly condition_count: number;
  readonly analysis_count: number;
  readonly review_status: ReviewStatus;
}

export interface ConditionResponse {
  readonly condition_id: string;
  readonly name: string;
  readonly evidence_quote: string;
  readonly documentation_status: DocumentationStatus;
  readonly icd10_code: string | null;
  readonly confidence: number;
}

export interface DocumentationGapResponse {
  readonly gap_id: string;
  readonly description: string;
  readonly related_condition_id: string | null;
  readonly severity: GapSeverity;
}

export interface AnalysisOutputResponse {
  readonly summary: string;
  readonly conditions: readonly ConditionResponse[];
  readonly documentation_gaps: readonly DocumentationGapResponse[];
}

export interface QuoteVerificationResponse {
  readonly condition_id: string;
  readonly status: QuoteVerificationStatus;
  readonly match_score: number;
  readonly match_offset: number | null;
  readonly match_length: number | null;
}

export interface VerificationReportResponse {
  readonly checked_at: string;
  readonly quote_results: readonly QuoteVerificationResponse[];
  readonly verified_count: number;
  readonly unverified_count: number;
}

export interface AnalysisFailureResponse {
  readonly code: string;
  readonly message: string;
}

export interface AnalysisResponse {
  readonly analysis_id: string;
  readonly note_id: string;
  readonly status: AnalysisStatus;
  readonly provider: ProviderName;
  readonly model_id: string;
  readonly prompt_version: string;
  readonly output: AnalysisOutputResponse | null;
  readonly verification: VerificationReportResponse | null;
  readonly failure: AnalysisFailureResponse | null;
  readonly latency_ms: number;
  readonly cache_hit: boolean;
  readonly created_at: string;
}

export interface ReviewedConditionResponse {
  readonly condition_id: string;
  readonly origin: ConditionOrigin;
  readonly action: ReviewAction;
  readonly name: string;
  readonly evidence_quote: string;
  readonly documentation_status: DocumentationStatus;
  readonly icd10_code: string | null;
  readonly rejection_reason: string | null;
}

export interface ReviewedGapResponse {
  readonly gap_id: string;
  readonly origin: ConditionOrigin;
  readonly action: ReviewAction;
  readonly description: string;
}

export interface ReviewResponse {
  readonly review_id: string;
  readonly analysis_id: string;
  readonly note_id: string;
  readonly version: number;
  readonly reviewed_conditions: readonly ReviewedConditionResponse[];
  readonly reviewed_gaps: readonly ReviewedGapResponse[];
  readonly summary_override: string | null;
  readonly reviewer_note: string | null;
  readonly created_at: string;
}

export interface PageResponse<TItem> {
  readonly items: readonly TItem[];
  readonly next_cursor: string | null;
}

export interface CreateNoteRequest {
  readonly content: string;
  readonly pseudonym?: string | null;
  readonly visit_date?: string | null;
}

export interface RunAnalysisRequest {
  readonly force: boolean;
}

export interface ApiErrorDetail {
  readonly field: string;
  readonly message: string;
}

export interface ApiErrorBody {
  readonly error: {
    readonly code: string;
    readonly message: string;
    readonly details: readonly ApiErrorDetail[] | null;
    readonly request_id: string;
  };
}

import { apiClient } from '@/services/apiClient';
import type { ReviewResponse } from '@/types/api';

export function submitReview(
  analysisId: string,
  payload: {
    reviewed_conditions: readonly unknown[];
    reviewed_gaps: readonly unknown[];
    reviewer_note: string | null;
  },
): Promise<ReviewResponse> {
  return apiClient.post<ReviewResponse>(`/api/v1/analyses/${analysisId}/reviews`, payload);
}

export function fetchReviewsForAnalysis(
  analysisId: string,
  signal?: AbortSignal,
): Promise<readonly ReviewResponse[]> {
  return apiClient.get<readonly ReviewResponse[]>(
    `/api/v1/analyses/${analysisId}/reviews`,
    signal,
  );
}

import { apiClient } from '@/services/apiClient';
import type {
  AnalysisResponse,
  CreateNoteRequest,
  NoteResponse,
  NoteSummaryResponse,
  PageResponse,
  RunAnalysisRequest,
  UserResponse,
} from '@/types/api';

export function fetchCurrentUser(signal?: AbortSignal): Promise<UserResponse> {
  return apiClient.get<UserResponse>('/api/v1/users/me', signal);
}

export function createNote(payload: CreateNoteRequest): Promise<NoteResponse> {
  return apiClient.post<NoteResponse>('/api/v1/notes', payload);
}

export function fetchNote(noteId: string, signal?: AbortSignal): Promise<NoteResponse> {
  return apiClient.get<NoteResponse>(`/api/v1/notes/${noteId}`, signal);
}

export function fetchNoteHistory(
  params: { limit?: number; cursor?: string | null },
  signal?: AbortSignal,
): Promise<PageResponse<NoteSummaryResponse>> {
  const query = new URLSearchParams();
  query.set('limit', String(params.limit ?? 20));
  if (params.cursor !== undefined && params.cursor !== null) {
    query.set('cursor', params.cursor);
  }
  return apiClient.get<PageResponse<NoteSummaryResponse>>(
    `/api/v1/notes?${query.toString()}`,
    signal,
  );
}

export function runAnalysis(noteId: string, force = false): Promise<AnalysisResponse> {
  const payload: RunAnalysisRequest = { force };
  return apiClient.post<AnalysisResponse>(`/api/v1/notes/${noteId}/analyses`, payload);
}

export function fetchAnalysesForNote(
  noteId: string,
  signal?: AbortSignal,
): Promise<readonly AnalysisResponse[]> {
  return apiClient.get<readonly AnalysisResponse[]>(`/api/v1/notes/${noteId}/analyses`, signal);
}

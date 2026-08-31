/**
 * The only module in the application that calls `fetch`.
 *
 * It attaches the Firebase ID token, retries once on a 401 with a force-refreshed
 * token, and narrows the backend's error envelope into a typed ApiError. No
 * component ever sees an untyped payload or a raw Response.
 */

import { auth } from '@/lib/firebase';
import { env } from '@/config/env';
import type { ApiErrorBody, ApiErrorDetail } from '@/types/api';

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: readonly ApiErrorDetail[] | null;
  readonly requestId: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(params: {
    code: string;
    message: string;
    status: number;
    details: readonly ApiErrorDetail[] | null;
    requestId: string | null;
    retryAfterSeconds: number | null;
  }) {
    super(params.message);
    this.name = 'ApiError';
    this.code = params.code;
    this.status = params.status;
    this.details = params.details;
    this.requestId = params.requestId;
    this.retryAfterSeconds = params.retryAfterSeconds;
  }

  /** True when retrying the same request later could plausibly succeed. */
  get isRetryable(): boolean {
    return this.status === 503 || this.status === 429 || this.status === 0;
  }
}

const NETWORK_ERROR = new ApiError({
  code: 'NETWORK_UNAVAILABLE',
  message: 'Could not reach the server. Check your connection and try again.',
  status: 0,
  details: null,
  requestId: null,
  retryAfterSeconds: null,
});

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false;
  }
  const candidate = (value as { error: unknown }).error;
  return (
    typeof candidate === 'object' &&
    candidate !== null &&
    'code' in candidate &&
    'message' in candidate
  );
}

async function toApiError(response: Response): Promise<ApiError> {
  const retryAfter = response.headers.get('Retry-After');
  let body: unknown = null;

  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (isApiErrorBody(body)) {
    return new ApiError({
      code: body.error.code,
      message: body.error.message,
      status: response.status,
      details: body.error.details,
      requestId: body.error.request_id,
      retryAfterSeconds: retryAfter === null ? null : Number.parseInt(retryAfter, 10),
    });
  }

  return new ApiError({
    code: 'UNEXPECTED_RESPONSE',
    message: `The server returned an unexpected ${String(response.status)} response.`,
    status: response.status,
    details: null,
    requestId: response.headers.get('X-Request-ID'),
    retryAfterSeconds: null,
  });
}

async function authorizationHeader(forceRefresh: boolean): Promise<string | null> {
  const user = auth.currentUser;
  if (user === null) {
    return null;
  }
  const token = await user.getIdToken(forceRefresh);
  return `Bearer ${token}`;
}

interface RequestOptions {
  readonly method: 'GET' | 'POST';
  readonly path: string;
  readonly body?: unknown;
  readonly signal?: AbortSignal;
}

async function send(options: RequestOptions, forceRefresh: boolean): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = await authorizationHeader(forceRefresh);

  if (token !== null) {
    headers.Authorization = token;
  }
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  const init: RequestInit = {
    method: options.method,
    headers,
    ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
    ...(options.signal === undefined ? {} : { signal: options.signal }),
  };

  return fetch(`${env.apiBaseUrl}${options.path}`, init);
}

async function request<TResponse>(options: RequestOptions): Promise<TResponse> {
  let response: Response;

  try {
    response = await send(options, false);
  } catch {
    throw NETWORK_ERROR;
  }

  // A 401 usually means the cached ID token expired mid-session. Refresh once
  // and retry before deciding the user is signed out.
  if (response.status === 401 && auth.currentUser !== null) {
    try {
      response = await send(options, true);
    } catch {
      throw NETWORK_ERROR;
    }
  }

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return (await response.json()) as TResponse;
}

export const apiClient = {
  get: <TResponse>(path: string, signal?: AbortSignal): Promise<TResponse> =>
    request<TResponse>({ method: 'GET', path, ...(signal === undefined ? {} : { signal }) }),

  post: <TResponse>(path: string, body: unknown, signal?: AbortSignal): Promise<TResponse> =>
    request<TResponse>({
      method: 'POST',
      path,
      body,
      ...(signal === undefined ? {} : { signal }),
    }),
};

/**
 * Wakes a cold backend while the user is still typing their password.
 * Render's free tier spins down after 15 minutes idle.
 */
export async function pingHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${env.apiBaseUrl}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * One request state machine, shared by every data-fetching view.
 *
 * Centralised so no screen invents its own `loading` boolean and forgets the
 * error branch. The discriminated union makes forgetting it a type error.
 */

import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '@/services/apiClient';

export type AsyncState<TData> =
  | { readonly status: 'loading' }
  | { readonly status: 'success'; readonly data: TData }
  | { readonly status: 'error'; readonly error: ApiError };

function toApiError(caught: unknown): ApiError {
  return caught instanceof ApiError
    ? caught
    : new ApiError({
        code: 'UNEXPECTED',
        message: 'Something went wrong loading this page.',
        status: 0,
        details: null,
        requestId: null,
        retryAfterSeconds: null,
      });
}

export function useAsync<TData>(
  loader: (signal: AbortSignal) => Promise<TData>,
  dependencies: readonly unknown[],
): { readonly state: AsyncState<TData>; readonly reload: () => void } {
  const [state, setState] = useState<AsyncState<TData>>({ status: 'loading' });
  const [reloadToken, setReloadToken] = useState(0);

  const reload = useCallback(() => {
    setReloadToken((token) => token + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });

    loader(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ status: 'success', data });
        }
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setState({ status: 'error', error: toApiError(caught) });
        }
      });

    return () => {
      controller.abort();
    };
    // `loader` is intentionally excluded: callers pass an inline closure, and
    // the explicit dependency list is what controls refetching.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, reloadToken]);

  return { state, reload };
}

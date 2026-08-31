/**
 * The states every asynchronous view needs.
 *
 * Centralised so no screen invents its own way of saying "loading", "empty" or
 * "this failed" — and so no screen can quietly skip one.
 */

import type { ReactNode } from 'react';

import styles from './Feedback.module.css';

export function Spinner({ label }: { label: string }): JSX.Element {
  return (
    <span className={styles.spinner} role="status" aria-live="polite">
      <span className={styles.spinnerRing} aria-hidden="true" />
      <span className={styles.spinnerLabel}>{label}</span>
    </span>
  );
}

export function LoadingState({ message }: { message: string }): JSX.Element {
  return (
    <div className={styles.block}>
      <Spinner label={message} />
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode | undefined;
}): JSX.Element {
  return (
    <div className={styles.block}>
      <p className={styles.emptyTitle}>{title}</p>
      <p className={styles.emptyDescription}>{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({
  title,
  message,
  requestId,
  onRetry,
}: {
  title: string;
  message: string;
  requestId?: string | null | undefined;
  onRetry?: (() => void) | undefined;
}): JSX.Element {
  return (
    <div className={styles.error} role="alert">
      <p className={styles.errorTitle}>{title}</p>
      <p className={styles.errorMessage}>{message}</p>
      {onRetry !== undefined && (
        <button type="button" className={styles.retry} onClick={onRetry}>
          Try again
        </button>
      )}
      {requestId !== undefined && requestId !== null && (
        <p className={styles.requestId}>Reference: {requestId}</p>
      )}
    </div>
  );
}

/**
 * Status badges.
 *
 * Documentation status is the primary scanning signal in this product, so the
 * mapping from status to colour and label lives in exactly one place and every
 * variant is exhaustive over its union — an added status becomes a compile
 * error rather than an unstyled badge.
 */

import type {
  DocumentationStatus,
  GapSeverity,
  QuoteVerificationStatus,
  ReviewStatus,
} from '@/types/api';

import styles from './Badge.module.css';

const DOCUMENTATION_LABELS: Record<DocumentationStatus, string> = {
  well_documented: 'Well documented',
  ambiguous: 'Ambiguous',
  mentioned_without_plan: 'No assessment or plan',
};

const DOCUMENTATION_TONES: Record<DocumentationStatus, string> = {
  well_documented: styles.good,
  ambiguous: styles.warn,
  mentioned_without_plan: styles.bad,
};

export function DocumentationStatusBadge({
  status,
}: {
  status: DocumentationStatus;
}): JSX.Element {
  return (
    <span className={`${styles.badge} ${DOCUMENTATION_TONES[status]}`}>
      {DOCUMENTATION_LABELS[status]}
    </span>
  );
}

const SEVERITY_LABELS: Record<GapSeverity, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

const SEVERITY_TONES: Record<GapSeverity, string> = {
  high: styles.bad,
  medium: styles.warn,
  low: styles.neutral,
};

export function SeverityBadge({ severity }: { severity: GapSeverity }): JSX.Element {
  return (
    <span className={`${styles.badge} ${SEVERITY_TONES[severity]}`}>
      {SEVERITY_LABELS[severity]}
    </span>
  );
}

const REVIEW_LABELS: Record<ReviewStatus, string> = {
  reviewed: 'Reviewed',
  pending: 'Pending review',
};

export function ReviewStatusBadge({ status }: { status: ReviewStatus }): JSX.Element {
  return (
    <span
      className={`${styles.badge} ${status === 'reviewed' ? styles.good : styles.neutral}`}
    >
      {REVIEW_LABELS[status]}
    </span>
  );
}

const VERIFICATION_LABELS: Record<QuoteVerificationStatus, string> = {
  exact: 'Evidence verified',
  normalized: 'Evidence verified',
  fuzzy: 'Evidence closely matched',
  not_found: 'Quote not found in note',
};

/**
 * An unverified quote must be impossible to miss: it is the one signal that
 * tells a clinician the machine may have invented something.
 */
export function EvidenceBadge({
  status,
}: {
  status: QuoteVerificationStatus;
}): JSX.Element {
  const isVerified = status !== 'not_found';

  return (
    <span
      className={`${styles.badge} ${isVerified ? styles.verified : styles.unverified}`}
      title={
        isVerified
          ? 'This quote was located in the original note.'
          : 'This quote could not be located in the note. Treat it as unverified.'
      }
    >
      {isVerified ? '✓' : '⚠'} {VERIFICATION_LABELS[status]}
    </span>
  );
}

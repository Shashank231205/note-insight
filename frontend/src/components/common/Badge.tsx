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
  assembled: 'Quote pieced together from separate passages',
  not_found: 'Quote not found in note',
};

const VERIFICATION_TITLES: Record<QuoteVerificationStatus, string> = {
  exact: 'This quote was located in the original note.',
  normalized: 'This quote was located in the original note.',
  fuzzy: 'This quote was located in the original note.',
  assembled:
    'Each part of this quote appears in the note, but not together and not in this order. ' +
    'The wording is the clinician’s; the passage is not. Check it before accepting.',
  not_found: 'This quote could not be located in the note. Treat it as unverified.',
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
  // Assembled quotes are not evidence: no such passage exists in the note.
  // They are shown differently from a fabrication because the distinction is
  // actionable — the words are real, the citation is not.
  const isVerified = status !== 'not_found' && status !== 'assembled';

  return (
    <span
      className={`${styles.badge} ${isVerified ? styles.verified : styles.unverified}`}
      title={VERIFICATION_TITLES[status]}
    >
      {isVerified ? '✓' : '⚠'} {VERIFICATION_LABELS[status]}
    </span>
  );
}

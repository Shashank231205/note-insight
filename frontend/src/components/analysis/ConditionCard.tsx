import { DocumentationStatusBadge, EvidenceBadge } from '@/components/common/Badge';
import type { ConditionResponse, QuoteVerificationResponse } from '@/types/api';

import styles from './ConditionCard.module.css';

function ConfidenceMeter({ value }: { value: number }): JSX.Element {
  const percent = Math.round(value * 100);

  return (
    <div className={styles.confidence}>
      <span className={styles.confidenceLabel}>Confidence</span>
      <span
        className={styles.confidenceTrack}
        role="meter"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Model confidence ${String(percent)} percent`}
      >
        <span className={styles.confidenceFill} style={{ width: `${String(percent)}%` }} />
      </span>
      <span className={styles.confidenceValue}>{percent}%</span>
    </div>
  );
}

export function ConditionCard({
  condition,
  verification,
  onHighlight,
}: {
  condition: ConditionResponse;
  verification: QuoteVerificationResponse | undefined;
  onHighlight?: ((conditionId: string | null) => void) | undefined;
}): JSX.Element {
  // Assembled counts as unverified: the fragments are real, but the passage
  // the model claims to quote does not exist in the note.
  const isUnverified =
    verification?.status === 'not_found' || verification?.status === 'assembled';

  return (
    <article
      className={isUnverified ? styles.cardUnverified : styles.card}
      onMouseEnter={() => onHighlight?.(condition.condition_id)}
      onMouseLeave={() => onHighlight?.(null)}
    >
      <header className={styles.header}>
        <h3 className={styles.name}>{condition.name}</h3>
        <div className={styles.badges}>
          <DocumentationStatusBadge status={condition.documentation_status} />
          {verification !== undefined && <EvidenceBadge status={verification.status} />}
        </div>
      </header>

      <blockquote className={styles.quote}>{condition.evidence_quote}</blockquote>

      {isUnverified && (
        <p className={styles.warning}>
          This quote could not be located in the note. The model may have
          invented it — verify before accepting.
        </p>
      )}

      <footer className={styles.footer}>
        <span className={styles.code}>
          {condition.icd10_code ?? 'No code — note too non-specific'}
        </span>
        <ConfidenceMeter value={condition.confidence} />
      </footer>
    </article>
  );
}

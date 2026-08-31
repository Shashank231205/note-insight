import { ConditionCard } from '@/components/analysis/ConditionCard';
import { SeverityBadge } from '@/components/common/Badge';
import { EmptyState, ErrorState } from '@/components/common/Feedback';
import type { AnalysisResponse, QuoteVerificationResponse } from '@/types/api';

import styles from './AnalysisPanel.module.css';

function verificationIndex(
  analysis: AnalysisResponse,
): ReadonlyMap<string, QuoteVerificationResponse> {
  return new Map(
    (analysis.verification?.quote_results ?? []).map((result) => [result.condition_id, result]),
  );
}

/**
 * Renders one analysis, honestly.
 *
 * An analysis whose output failed validation is shown as exactly that — not as
 * an empty result, and not as a spinner that never resolves.
 */
export function AnalysisPanel({
  analysis,
  onHighlight,
  onReanalyze,
}: {
  analysis: AnalysisResponse;
  onHighlight?: ((conditionId: string | null) => void) | undefined;
  onReanalyze?: (() => void) | undefined;
}): JSX.Element {
  if (analysis.status !== 'succeeded' || analysis.output === null) {
    return (
      <ErrorState
        title="The model returned output we could not trust"
        message={
          analysis.failure?.message ??
          'The analysis could not be validated against the expected schema.'
        }
        onRetry={onReanalyze}
      />
    );
  }

  const { output } = analysis;
  const verifications = verificationIndex(analysis);
  const unverified = analysis.verification?.unverified_count ?? 0;

  return (
    <section className={styles.panel}>
      <header className={styles.summary}>
        <h2 className={styles.summaryTitle}>Encounter summary</h2>
        <p className={styles.summaryText}>{output.summary}</p>
        <dl className={styles.meta}>
          <div>
            <dt>Conditions</dt>
            <dd>{output.conditions.length}</dd>
          </div>
          <div>
            <dt>Gaps</dt>
            <dd>{output.documentation_gaps.length}</dd>
          </div>
          <div>
            <dt>Unverified quotes</dt>
            <dd className={unverified > 0 ? styles.metaAlert : undefined}>{unverified}</dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{analysis.model_id}</dd>
          </div>
        </dl>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Conditions</h2>
        {output.conditions.length === 0 ? (
          <EmptyState
            title="No conditions identified"
            description="The model found no codeable condition addressed in this note. That can be correct — review the note and add anything it missed."
          />
        ) : (
          <div className={styles.cards}>
            {output.conditions.map((condition) => (
              <ConditionCard
                key={condition.condition_id}
                condition={condition}
                verification={verifications.get(condition.condition_id)}
                {...(onHighlight === undefined ? {} : { onHighlight })}
              />
            ))}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Documentation gaps</h2>
        {output.documentation_gaps.length === 0 ? (
          <EmptyState
            title="No gaps flagged"
            description="Nothing a coding specialist would need to query back."
          />
        ) : (
          <ul className={styles.gaps}>
            {output.documentation_gaps.map((gap) => (
              <li key={gap.gap_id} className={styles.gap}>
                <SeverityBadge severity={gap.severity} />
                <span>{gap.description}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}

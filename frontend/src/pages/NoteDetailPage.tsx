import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { AnalysisPanel } from '@/components/analysis/AnalysisPanel';
import { EmptyState, ErrorState, LoadingState, Spinner } from '@/components/common/Feedback';
import { NoteHighlighter } from '@/components/notes/NoteHighlighter';
import { ReviewPanel } from '@/components/review/ReviewPanel';
import { useAsync } from '@/hooks/useAsync';
import { ApiError } from '@/services/apiClient';
import { fetchAnalysesForNote, fetchNote, runAnalysis } from '@/services/notesApi';
import { fetchReviewsForAnalysis } from '@/services/reviewsApi';
import type { AnalysisResponse, NoteResponse, ReviewResponse } from '@/types/api';
import { formatDate, formatDateTime } from '@/utils/text';

import styles from './NoteDetailPage.module.css';

type Mode = 'view' | 'review';

interface NoteDetail {
  readonly note: NoteResponse;
  readonly analyses: readonly AnalysisResponse[];
  readonly latestReview: ReviewResponse | null;
}

export function NoteDetailPage(): JSX.Element {
  const { noteId } = useParams<{ noteId: string }>();
  const [activeConditionId, setActiveConditionId] = useState<string | null>(null);
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<ApiError | null>(null);
  const [mode, setMode] = useState<Mode>('view');

  const { state, reload } = useAsync<NoteDetail>(
    async (signal) => {
      const id = noteId ?? '';
      const [note, analyses] = await Promise.all([
        fetchNote(id, signal),
        fetchAnalysesForNote(id, signal),
      ]);

      const newest = analyses.at(0) ?? null;
      const reviews =
        newest === null ? [] : await fetchReviewsForAnalysis(newest.analysis_id, signal);

      return { note, analyses, latestReview: reviews.at(0) ?? null };
    },
    [noteId],
  );

  const handleAnalyze = useCallback(
    (force: boolean) => {
      if (noteId === undefined) {
        return;
      }
      setAnalysisError(null);
      setIsReanalyzing(true);

      void runAnalysis(noteId, force)
        .then(() => {
          reload();
        })
        .catch((caught: unknown) => {
          if (caught instanceof ApiError) {
            setAnalysisError(caught);
          }
        })
        .finally(() => {
          setIsReanalyzing(false);
        });
    },
    [noteId, reload],
  );

  if (state.status === 'loading') {
    return <LoadingState message="Loading the note…" />;
  }

  if (state.status === 'error') {
    return (
      <ErrorState
        title={state.error.status === 404 ? 'Note not found' : 'Could not load this note'}
        message={
          state.error.status === 404
            ? 'This note does not exist, or it belongs to another account.'
            : state.error.message
        }
        requestId={state.error.requestId}
        onRetry={reload}
      />
    );
  }

  const { note, analyses, latestReview } = state.data;
  const latest = analyses.at(0) ?? null;
  const canReview = latest !== null && latest.status === 'succeeded';

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <Link className={styles.back} to="/notes">
            ← History
          </Link>
          <h1 className={styles.title}>{note.pseudonym ?? 'Untitled note'}</h1>
          <p className={styles.meta}>
            {note.visit_date !== null && <>Visit {formatDate(note.visit_date)} · </>}
            Submitted {formatDateTime(note.created_at)} · {note.word_count} words ·{' '}
            {note.analysis_count} {note.analysis_count === 1 ? 'analysis' : 'analyses'}
          </p>
        </div>

        <button
          type="button"
          className={styles.reanalyze}
          disabled={isReanalyzing}
          onClick={() => {
            handleAnalyze(latest !== null);
          }}
        >
          {isReanalyzing ? (
            <Spinner label="Analyzing…" />
          ) : latest === null ? (
            'Analyze note'
          ) : (
            'Re-analyze'
          )}
        </button>
      </header>

      {analysisError !== null && (
        <ErrorState
          title={
            analysisError.isRetryable
              ? 'The analysis service is temporarily unavailable'
              : 'The analysis could not be run'
          }
          message={
            analysisError.retryAfterSeconds === null
              ? analysisError.message
              : `${analysisError.message} Try again in ${String(analysisError.retryAfterSeconds)} seconds.`
          }
          requestId={analysisError.requestId}
          onRetry={() => {
            handleAnalyze(true);
          }}
        />
      )}

      <div className={styles.columns}>
        <section className={styles.noteColumn}>
          <h2 className={styles.columnTitle}>Original note</h2>
          <NoteHighlighter
            content={note.content}
            verifications={latest?.verification?.quote_results ?? []}
            conditions={latest?.output?.conditions ?? []}
            activeConditionId={activeConditionId}
          />
          <p className={styles.legend}>
            Highlighted spans are the evidence the model cited, located in your
            note by the verifier.
          </p>
        </section>

        <section className={styles.analysisColumn}>
          {canReview && (
            <div className={styles.modeSwitch} role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'view'}
                className={mode === 'view' ? styles.modeActive : styles.mode}
                onClick={() => {
                  setMode('view');
                }}
              >
                Model output
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'review'}
                className={mode === 'review' ? styles.modeActive : styles.mode}
                onClick={() => {
                  setMode('review');
                }}
              >
                {latestReview === null ? 'Review' : 'Edit review'}
              </button>
            </div>
          )}

          {latest === null && (
            <EmptyState
              title="Not analyzed yet"
              description="This note is saved but has no analysis. Run one when you are ready."
            />
          )}

          {latest !== null && mode === 'view' && (
            <AnalysisPanel
              analysis={latest}
              onHighlight={setActiveConditionId}
              onReanalyze={() => {
                handleAnalyze(true);
              }}
            />
          )}

          {latest !== null && mode === 'review' && canReview && (
            <ReviewPanel
              analysis={latest}
              savedReview={latestReview}
              onSubmitted={() => {
                setMode('view');
                reload();
              }}
            />
          )}
        </section>
      </div>

      {analyses.length > 1 && (
        <section className={styles.previous}>
          <h2 className={styles.columnTitle}>Earlier analyses</h2>
          <p className={styles.legend}>
            Re-analysing never deletes a previous result. Each row records the
            prompt version it ran under.
          </p>
          <ul className={styles.previousList}>
            {analyses.slice(1).map((analysis) => (
              <li key={analysis.analysis_id} className={styles.previousRow}>
                <span>{formatDateTime(analysis.created_at)}</span>
                <span className={styles.mono}>
                  {analysis.model_id} · prompt {analysis.prompt_version}
                </span>
                <span>
                  {analysis.status === 'succeeded'
                    ? `${String(analysis.output?.conditions.length ?? 0)} conditions`
                    : 'Invalid output'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

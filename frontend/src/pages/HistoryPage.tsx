import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ReviewStatusBadge } from '@/components/common/Badge';
import { EmptyState, ErrorState, LoadingState } from '@/components/common/Feedback';
import { useAsync } from '@/hooks/useAsync';
import { fetchNoteHistory } from '@/services/notesApi';
import { formatDate, formatDateTime } from '@/utils/text';

import styles from './HistoryPage.module.css';

export function HistoryPage(): JSX.Element {
  const [cursor, setCursor] = useState<string | null>(null);
  const { state, reload } = useAsync(
    (signal) => fetchNoteHistory({ cursor }, signal),
    [cursor],
  );

  if (state.status === 'loading') {
    return <LoadingState message="Loading your notes…" />;
  }

  if (state.status === 'error') {
    return (
      <ErrorState
        title="Could not load your notes"
        message={state.error.message}
        requestId={state.error.requestId}
        onRetry={reload}
      />
    );
  }

  const { items, next_cursor: nextCursor } = state.data;

  if (items.length === 0) {
    return (
      <EmptyState
        title="No notes yet"
        description="Analyzed notes appear here, newest first, with your corrections preserved."
        action={
          <Link className={styles.cta} to="/notes/new">
            Analyze your first note
          </Link>
        }
      />
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Note history</h1>
        <p className={styles.subtitle}>Most recent first.</p>
      </header>

      <ul className={styles.list}>
        {items.map((note) => (
          <li key={note.note_id}>
            <Link className={styles.row} to={`/notes/${note.note_id}`}>
              <span className={styles.pseudonym}>
                {note.pseudonym ?? <span className={styles.muted}>No pseudonym</span>}
              </span>
              <span className={styles.date}>
                {note.visit_date === null
                  ? formatDateTime(note.created_at)
                  : formatDate(note.visit_date)}
              </span>
              <span className={styles.count}>
                {note.condition_count}{' '}
                {note.condition_count === 1 ? 'condition' : 'conditions'}
              </span>
              <ReviewStatusBadge status={note.review_status} />
            </Link>
          </li>
        ))}
      </ul>

      <div className={styles.pagination}>
        {cursor !== null && (
          <button
            type="button"
            className={styles.pageButton}
            onClick={() => {
              setCursor(null);
            }}
          >
            Back to newest
          </button>
        )}
        {nextCursor !== null && (
          <button
            type="button"
            className={styles.pageButton}
            onClick={() => {
              setCursor(nextCursor);
            }}
          >
            Older notes
          </button>
        )}
      </div>
    </div>
  );
}

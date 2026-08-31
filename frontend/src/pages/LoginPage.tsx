import { FirebaseError } from 'firebase/app';
import { useEffect, useState, type FormEvent } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '@/hooks/useAuth';
import { pingHealth } from '@/services/apiClient';

import styles from './LoginPage.module.css';

type Mode = 'sign-in' | 'sign-up';

const MINIMUM_PASSWORD_LENGTH = 8;

/** Firebase error codes are stable; its default messages are not user-facing. */
const AUTH_MESSAGES: Record<string, string> = {
  'auth/invalid-credential': 'That email and password combination was not recognised.',
  'auth/invalid-email': 'That does not look like a valid email address.',
  'auth/user-not-found': 'That email and password combination was not recognised.',
  'auth/wrong-password': 'That email and password combination was not recognised.',
  'auth/email-already-in-use': 'An account already exists for this email. Sign in instead.',
  'auth/weak-password': `Choose a password of at least ${String(MINIMUM_PASSWORD_LENGTH)} characters.`,
  'auth/too-many-requests': 'Too many attempts. Wait a moment and try again.',
  'auth/network-request-failed': 'Could not reach the authentication service.',
};

function messageFor(error: unknown): string {
  if (error instanceof FirebaseError) {
    return AUTH_MESSAGES[error.code] ?? 'Sign-in failed. Please try again.';
  }
  return 'Something went wrong. Please try again.';
}

export function LoginPage(): JSX.Element {
  const { user, isInitializing, signIn, signUp } = useAuth();
  const [mode, setMode] = useState<Mode>('sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isBackendCold, setIsBackendCold] = useState(false);

  useEffect(() => {
    // The backend sleeps on the free tier. Wake it while the user types, and
    // say so if it is slow rather than letting the first action hang.
    const timer = window.setTimeout(() => {
      setIsBackendCold(true);
    }, 2000);

    void pingHealth().then(() => {
      window.clearTimeout(timer);
      setIsBackendCold(false);
    });

    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  if (!isInitializing && user !== null) {
    return <Navigate to="/notes/new" replace />;
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    setError(null);

    if (mode === 'sign-up' && password.length < MINIMUM_PASSWORD_LENGTH) {
      setError(`Choose a password of at least ${String(MINIMUM_PASSWORD_LENGTH)} characters.`);
      return;
    }

    setIsSubmitting(true);
    const action = mode === 'sign-in' ? signIn : signUp;

    void action(email, password)
      .catch((caught: unknown) => {
        setError(messageFor(caught));
      })
      .finally(() => {
        setIsSubmitting(false);
      });
  };

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <h1 className={styles.title}>Note Insight</h1>
        <p className={styles.subtitle}>
          Structured documentation review for clinical notes.
        </p>

        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <label className={styles.field}>
            <span className={styles.label}>Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
              }}
            />
          </label>

          <label className={styles.field}>
            <span className={styles.label}>Password</span>
            <input
              type="password"
              autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'}
              required
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
              }}
            />
          </label>

          {error !== null && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          <button type="submit" className={styles.submit} disabled={isSubmitting}>
            {isSubmitting
              ? 'Working…'
              : mode === 'sign-in'
                ? 'Sign in'
                : 'Create account'}
          </button>
        </form>

        <button
          type="button"
          className={styles.toggle}
          onClick={() => {
            setMode(mode === 'sign-in' ? 'sign-up' : 'sign-in');
            setError(null);
          }}
        >
          {mode === 'sign-in'
            ? 'No account yet? Create one'
            : 'Already have an account? Sign in'}
        </button>

        {isBackendCold && (
          <p className={styles.notice}>
            Waking the server — the free tier sleeps when idle, so the first
            request can take up to a minute.
          </p>
        )}

        <p className={styles.privacy}>
          Use synthetic notes only. Never enter real patient identifiers.
        </p>
      </div>
    </main>
  );
}

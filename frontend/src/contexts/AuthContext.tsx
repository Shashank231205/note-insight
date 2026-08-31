import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  type User,
} from 'firebase/auth';
import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { auth } from '@/lib/firebase';

export interface AuthContextValue {
  readonly user: User | null;
  /** True until Firebase has restored any persisted session. */
  readonly isInitializing: boolean;
  readonly signIn: (email: string, password: string) => Promise<void>;
  readonly signUp: (email: string, password: string) => Promise<void>;
  readonly signOutUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    // Fires once immediately with the restored session, then on every change.
    // Until it fires, we cannot tell "signed out" from "not yet known", which
    // is why routes wait on isInitializing rather than redirecting early.
    return onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser);
      setIsInitializing(false);
    });
  }, []);

  const signIn = useCallback(async (email: string, password: string): Promise<void> => {
    await signInWithEmailAndPassword(auth, email, password);
  }, []);

  const signUp = useCallback(async (email: string, password: string): Promise<void> => {
    await createUserWithEmailAndPassword(auth, email, password);
  }, []);

  const signOutUser = useCallback(async (): Promise<void> => {
    await signOut(auth);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isInitializing, signIn, signUp, signOutUser }),
    [user, isInitializing, signIn, signUp, signOutUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

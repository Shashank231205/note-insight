/**
 * Firebase initialization — Authentication only.
 *
 * The Firestore SDK is deliberately absent. The browser never talks to the
 * database; every read and write goes through the API, where authorization is
 * implemented once and unit-tested. See docs/01-architecture.md §3.
 */

import { initializeApp, type FirebaseApp } from 'firebase/app';
import { getAuth, type Auth } from 'firebase/auth';

import { env } from '@/config/env';

const app: FirebaseApp = initializeApp({
  apiKey: env.firebase.apiKey,
  authDomain: env.firebase.authDomain,
  projectId: env.firebase.projectId,
  appId: env.firebase.appId,
});

export const auth: Auth = getAuth(app);

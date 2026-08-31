/**
 * Environment access, parsed and validated in exactly one place.
 *
 * A missing variable fails loudly at boot instead of surfacing as `undefined`
 * three layers deep inside the Firebase SDK.
 */

interface AppEnv {
  readonly apiBaseUrl: string;
  readonly firebase: {
    readonly apiKey: string;
    readonly authDomain: string;
    readonly projectId: string;
    readonly appId: string;
  };
}

function required(name: string, value: string | undefined): string {
  if (value === undefined || value.trim() === '') {
    throw new Error(
      `Missing required environment variable ${name}. Copy .env.example to .env.local and fill it in.`,
    );
  }
  return value.trim();
}

function readEnv(): AppEnv {
  const raw = import.meta.env;

  return {
    apiBaseUrl: required('VITE_API_BASE_URL', raw.VITE_API_BASE_URL).replace(/\/+$/, ''),
    firebase: {
      apiKey: required('VITE_FIREBASE_API_KEY', raw.VITE_FIREBASE_API_KEY),
      authDomain: required('VITE_FIREBASE_AUTH_DOMAIN', raw.VITE_FIREBASE_AUTH_DOMAIN),
      projectId: required('VITE_FIREBASE_PROJECT_ID', raw.VITE_FIREBASE_PROJECT_ID),
      appId: required('VITE_FIREBASE_APP_ID', raw.VITE_FIREBASE_APP_ID),
    },
  };
}

export const env: AppEnv = readEnv();

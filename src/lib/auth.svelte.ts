import type { Session } from '@supabase/supabase-js';
import { supabase } from './supabase';

export const MIN_PASSWORD_LENGTH = 8;

/**
 * Dev builds only: a bare ID like "foo" logs in as the seeded foo@isobath.local.
 * `import.meta.env.DEV` is statically false in production builds, so this branch is removed.
 */
export const DEV_LOGIN_IDS = import.meta.env.DEV;

export function loginEmail(input: string): string {
	return DEV_LOGIN_IDS && !input.includes('@') ? `${input}@isobath.local` : input;
}

class AuthState {
	session = $state<Session | null>(null);
	ready = $state(false);
}

export const auth = new AuthState();

let started = false;

/** Subscribe once to Supabase auth state (call from the root layout in the browser). */
export function startAuth(): void {
	if (started) return;
	started = true;
	const sb = supabase();
	void sb.auth.getSession().then(({ data }) => {
		auth.session = data.session;
		auth.ready = true;
	});
	sb.auth.onAuthStateChange((_event, session) => {
		auth.session = session;
		auth.ready = true;
	});
}

/** Same-origin relative path only; anything else is an open-redirect attempt. */
export function safeNext(next: string | null): string | null {
	return next && next.startsWith('/') && !next.startsWith('//') ? next : null;
}

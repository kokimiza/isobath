import type { Session } from '@supabase/supabase-js';
import { supabase } from './supabase';

export const MIN_PASSWORD_LENGTH = 8;

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
	sb.auth.getSession().then(({ data }) => {
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

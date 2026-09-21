import type { Session } from '@supabase/supabase-js';
import { api, type ConsentVersions } from './api.svelte';

let confirmedFor: string | null = null;

function sameVersions(a: unknown, b: ConsentVersions): boolean {
	if (!a || typeof a !== 'object') return false;
	return Object.entries(b).every(([doc, v]) => (a as Record<string, unknown>)[doc] === v);
}

/**
 * true when the user has agreed to the current documents (SEC-CON-01/02).
 * Consent given at signup is carried in user_metadata and recorded here on first login.
 */
export async function ensureConsent(session: Session): Promise<boolean> {
	if (confirmedFor === session.user.id) return true;
	const status = await api.consents();
	if (!status.complete && sameVersions(session.user.user_metadata?.consents, status.required)) {
		await api.agree(status.required);
		status.complete = true;
	}
	if (status.complete) confirmedFor = session.user.id;
	return status.complete;
}

export function markConsented(session: Session): void {
	confirmedFor = session.user.id;
}

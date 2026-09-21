import type { Session } from '@supabase/supabase-js';
import { api, type ConsentDocument, type ConsentVersions } from './api.svelte';

let confirmedFor: string | null = null;

/** Documents the user ticked at signup, if their versions are still current. */
function claimedAtSignup(session: Session, versions: ConsentVersions): Partial<ConsentVersions> {
	const claimed: unknown = session.user.user_metadata?.consents;
	if (!claimed || typeof claimed !== 'object') return {};
	const out: Partial<ConsentVersions> = {};
	for (const [doc, v] of Object.entries(claimed as Record<string, unknown>)) {
		const current = versions[doc as ConsentDocument];
		if (v === current) out[doc as ConsentDocument] = current;
	}
	return out;
}

/**
 * true when the required documents are agreed (SEC-CON-01/02).
 * Consent given at signup travels in user_metadata and is recorded here on first login.
 */
export async function ensureConsent(session: Session): Promise<boolean> {
	if (confirmedFor === session.user.id) return true;
	const status = await api.consents();
	if (!status.complete) {
		const claimed = claimedAtSignup(session, status.versions);
		if (Object.keys(status.required).every((doc) => doc in claimed)) {
			await api.agree(claimed);
			status.complete = true;
		}
	}
	if (status.complete) confirmedFor = session.user.id;
	return status.complete;
}

export function markConsented(session: Session): void {
	confirmedFor = session.user.id;
}

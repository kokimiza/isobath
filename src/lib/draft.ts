import type { Answer } from './api.svelte';
import { clearRegistration } from './registration';

// Unsent answers survive reloads (FR-SUR-07). Storage can be unavailable; never let it throw.
const key = (sessionId: string) => `isobath:draft:${sessionId}`;

export function loadDraft(sessionId: string): Answer[] {
	try {
		return JSON.parse(localStorage.getItem(key(sessionId)) ?? '[]') as Answer[];
	} catch {
		return [];
	}
}

/** On logout / account deletion: unsent answers must not outlive the session on this device. */
export function clearDrafts(): void {
	clearRegistration();
	try {
		for (const k of Object.keys(localStorage))
			if (k.startsWith('isobath:draft:')) localStorage.removeItem(k);
	} catch {
		// storage unavailable: nothing was stored
	}
}

export function saveDraft(sessionId: string, answers: Answer[]): boolean {
	try {
		if (answers.length) localStorage.setItem(key(sessionId), JSON.stringify(answers));
		else localStorage.removeItem(key(sessionId));
		return true;
	} catch {
		// The caller must warn before the in-memory draft can be lost.
		return false;
	}
}

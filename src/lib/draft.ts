import type { Answer } from './api.svelte';

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
	try {
		for (const k of Object.keys(localStorage))
			if (k.startsWith('isobath:draft:')) localStorage.removeItem(k);
	} catch {
		// storage unavailable: nothing was stored
	}
}

export function saveDraft(sessionId: string, answers: Answer[]): void {
	try {
		if (answers.length) localStorage.setItem(key(sessionId), JSON.stringify(answers));
		else localStorage.removeItem(key(sessionId));
	} catch {
		// private mode / quota: answers still live in memory
	}
}

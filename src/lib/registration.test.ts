import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import {
	currentRegistration,
	loadRegistration,
	saveRegistration,
	validDemographics,
} from './registration';
import type { Registration } from './api.svelte';

const registration: Registration = {
	birth_year: 2000,
	birth_month: 8,
	gender: 'prefer_not_to_say',
	adult_confirmed: true,
	non_diagnostic_confirmed: true,
	consents: [
		{ document: 'terms', version: '1' },
		{ document: 'privacy', version: '2' },
	],
};
beforeEach(() => {
	const store = new Map<string, string>();
	vi.stubGlobal('sessionStorage', {
		getItem: (key: string) => store.get(key) ?? null,
		setItem: (key: string, value: string) => store.set(key, value),
		removeItem: (key: string) => store.delete(key),
	});
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-08-31T15:00:00Z'));
});
afterEach(() => {
	vi.unstubAllGlobals();
	vi.useRealTimers();
});
test('registration expires and never silently accepts stale consent', () => {
	saveRegistration(registration);
	expect(loadRegistration()).toEqual(registration);
	expect(currentRegistration(registration, { terms: '1', privacy: '3', research: '2' })).toBe(
		false,
	);
	vi.advanceTimersByTime(24 * 60 * 60 * 1000);
	expect(loadRegistration()).toBeNull();
	expect(sessionStorage.getItem('isobath:registration')).toBeNull();
});
test('future months, invalid gender and malformed stored data are rejected', () => {
	expect(validDemographics(2026, '9', 'male')).toBe(true);
	expect(validDemographics(2026, '10', 'male')).toBe(false);
	expect(validDemographics(2000, '13', 'male')).toBe(false);
	expect(validDemographics(2000, '1', 'inferred')).toBe(false);
	sessionStorage.setItem('isobath:registration', '{"value":null}');
	expect(loadRegistration()).toBeNull();
});

import type { ConsentVersions, Registration } from './api.svelte';

const KEY = 'isobath:registration';
const MAX_AGE = 24 * 60 * 60 * 1000;
export const genders = ['male', 'female', 'neither', 'prefer_not_to_say'] as const;

export function validDemographics(
	year: number | undefined,
	month: string,
	gender: string,
): boolean {
	const parts = new Intl.DateTimeFormat('en-US', {
		timeZone: 'Asia/Tokyo',
		year: 'numeric',
		month: 'numeric',
	}).formatToParts(new Date());
	const currentYear = Number(parts.find((p) => p.type === 'year')?.value);
	const currentMonth = Number(parts.find((p) => p.type === 'month')?.value);
	return (
		Number.isInteger(year) &&
		!!year &&
		year > 0 &&
		year <= currentYear &&
		/^(?:[1-9]|1[0-2])$/.test(month) &&
		(year < currentYear || Number(month) <= currentMonth) &&
		genders.some((value) => value === gender)
	);
}

export function clearRegistration(): void {
	try {
		sessionStorage.removeItem(KEY);
	} catch {
		/* No persisted draft. */
	}
}

/** Only a tab-scoped, expiring draft; no Auth metadata or long-lived localStorage. */
export function saveRegistration(value: Registration): void {
	sessionStorage.setItem(KEY, JSON.stringify({ value, expires: Date.now() + MAX_AGE }));
}

export function loadRegistration(): Registration | null {
	try {
		const raw: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? 'null');
		if (!raw || typeof raw !== 'object') {
			clearRegistration();
			return null;
		}
		const draft = raw as { expires?: number; value?: Registration };
		const v = draft.value;
		if (
			typeof draft.expires !== 'number' ||
			draft.expires <= Date.now() ||
			draft.expires > Date.now() + MAX_AGE ||
			!v ||
			!validDemographics(v.birth_year, String(v.birth_month), v.gender) ||
			v.adult_confirmed !== true ||
			v.non_diagnostic_confirmed !== true ||
			!Array.isArray(v.consents) ||
			!v.consents.every(
				(c) =>
					['terms', 'privacy', 'research'].includes(c.document) && typeof c.version === 'string',
			)
		) {
			clearRegistration();
			return null;
		}
		return v;
	} catch {
		clearRegistration();
		return null;
	}
}

export function currentRegistration(draft: Registration, versions: ConsentVersions): boolean {
	return (
		['terms', 'privacy'].every((d) => draft.consents.some((c) => c.document === d)) &&
		draft.consents.every((c) => versions[c.document] === c.version)
	);
}

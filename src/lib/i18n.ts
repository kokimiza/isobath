import type { AuthError } from '@supabase/supabase-js';
import { m } from '$lib/paraglide/messages.js';
import { getLocale } from '$lib/paraglide/runtime';
import type { Stage } from './api.svelte';
import { signed } from './chart3d/geometry';

export const positionText = (position: number[]) =>
	position.length === 3
		? m.profile_position_value_3d({
				x: signed(position[0]),
				y: signed(position[1]),
				z: signed(position[2]),
			})
		: m.profile_position_value({ x: position[0].toFixed(2), y: position[1].toFixed(2) });

// PRIOR positions use question design and have not been calibrated with population data.
export const stageName = (stage: Stage) =>
	stage === 'PRIOR'
		? m.stage_PRIOR()
		: stage === 'CHARTED'
			? m.stage_CHARTED()
			: m.stage_COLLECTING();

export const stageDescription = (stage: Stage) =>
	stage === 'PRIOR'
		? m.stage_desc_PRIOR()
		: stage === 'CHARTED'
			? m.stage_desc_CHARTED()
			: m.stage_desc_COLLECTING();

export const likertLabels = [m.likert_1, m.likert_2, m.likert_3, m.likert_4, m.likert_5];

const authErrors: Record<string, () => string> = {
	invalid_credentials: m.auth_error_invalid_credentials,
	email_not_confirmed: m.auth_error_email_not_confirmed,
	user_already_exists: m.auth_error_user_exists,
	email_exists: m.auth_error_user_exists,
	weak_password: m.auth_error_weak_password,
	over_request_rate_limit: m.auth_error_rate_limit,
	over_email_send_rate_limit: m.auth_error_rate_limit,
};

export function authErrorMessage(error: AuthError): string {
	return (error.code ? authErrors[error.code]?.() : undefined) ?? m.auth_error_generic();
}

/** Nightly-update times are defined in Japan time (01:00 JST), so always show them in JST. */
export function formatUpdateTime(iso: string): string {
	return new Intl.DateTimeFormat(getLocale(), {
		timeZone: 'Asia/Tokyo',
		month: 'short',
		day: 'numeric',
		hour: 'numeric',
		minute: '2-digit',
		timeZoneName: 'short',
	}).format(new Date(iso));
}

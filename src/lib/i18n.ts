import type { AuthError } from '@supabase/supabase-js';
import { m } from '$lib/paraglide/messages.js';
import type { Stage } from './api.svelte';

export const stageName: Record<Stage, () => string> = {
	UNCHARTED: m.stage_UNCHARTED,
	'PRE-CHART': m.stage_PRE_CHART,
	PROTO: m.stage_PROTO,
	SEED: m.stage_SEED,
	CHART: m.stage_CHART,
};

export const stageDescription: Record<Stage, () => string> = {
	UNCHARTED: m.stage_desc_UNCHARTED,
	'PRE-CHART': m.stage_desc_PRE_CHART,
	PROTO: m.stage_desc_PROTO,
	SEED: m.stage_desc_SEED,
	CHART: m.stage_desc_CHART,
};

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

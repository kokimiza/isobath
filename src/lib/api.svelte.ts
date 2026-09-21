import { PUBLIC_API_BASE } from '$env/static/public';
import { m } from '$lib/paraglide/messages.js';
import { supabase } from './supabase';

export type Stage = 'UNCHARTED' | 'PRE-CHART' | 'PROTO' | 'SEED' | 'CHART';
export type ConsentDocument = 'terms' | 'privacy' | 'research';
export type ConsentVersions = Record<ConsentDocument, string>;

export interface Meta {
	chart: { version: string; stage: Stage };
	participants: number;
	emergency_level: number;
	signup_enabled: boolean;
	survey_write_enabled: boolean;
	consent_versions: ConsentVersions;
}

export interface Position {
	chart: { version: string; stage: Stage };
	observer_no: number;
	participants: number;
	survey: { initial_completed: boolean; open_session: boolean };
	position?: number[];
	se?: number[];
	confidence?: number;
	regions?: { lineage_id: string; p: number }[];
	near_boundary?: boolean;
}

export interface SurveySummary {
	id: string;
	kind: 'initial' | 'continuous';
	status: string;
	total: number;
	answered: number;
}

export interface Question {
	id: number;
	text: string;
}

export interface Answer {
	question_id: number;
	value: number;
	response_ms: number;
}

export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string
	) {
		super(code);
	}
}

const SLOW_AFTER_MS = 10_000; // Render Free cold start is ~1 min (FR-UI-03)
const TIMEOUT_MS = 90_000;

class NetState {
	slowRequests = $state(0);
	get slow() {
		return this.slowRequests > 0;
	}
}

export const net = new NetState();

interface RequestOptions {
	method?: 'GET' | 'POST' | 'DELETE';
	body?: unknown;
	auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
	const { method = 'GET', body, auth = true } = opts;
	const headers: Record<string, string> = {};
	if (body !== undefined) headers['content-type'] = 'application/json';
	if (auth) {
		const { data } = await supabase().auth.getSession();
		if (!data.session) throw new ApiError(401, 'unauthenticated');
		headers.authorization = `Bearer ${data.session.access_token}`;
	}

	let slow = false;
	const timer = setTimeout(() => {
		slow = true;
		net.slowRequests++;
	}, SLOW_AFTER_MS);
	let res: Response;
	try {
		res = await fetch(`${PUBLIC_API_BASE}${path}`, {
			method,
			headers,
			body: body === undefined ? undefined : JSON.stringify(body),
			signal: AbortSignal.timeout(TIMEOUT_MS)
		});
	} catch {
		throw new ApiError(0, 'network');
	} finally {
		clearTimeout(timer);
		if (slow) net.slowRequests--;
	}

	if (res.status === 401 && auth && !retried) {
		const { error } = await supabase().auth.refreshSession();
		if (!error) return request<T>(path, opts, true);
	}
	if (!res.ok) {
		const payload = await res.json().catch(() => null);
		throw new ApiError(res.status, payload?.error?.code ?? 'error');
	}
	return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
	meta: () => request<Meta>('/v1/meta', { auth: false }),
	position: () => request<Position>('/v1/me/position'),
	consents: () => request<{ required: ConsentVersions; complete: boolean }>('/v1/me/consents'),
	agree: (versions: Partial<ConsentVersions>) =>
		request<void>('/v1/me/consents', {
			method: 'POST',
			body: {
				consents: Object.entries(versions).map(([document, version]) => ({ document, version }))
			}
		}),
	createSurvey: (kind: SurveySummary['kind']) =>
		request<SurveySummary>('/v1/me/surveys', { method: 'POST', body: { kind } }),
	currentSurvey: () => request<SurveySummary & { questions: Question[] }>('/v1/me/surveys/current'),
	answer: (sessionId: string, answers: Answer[]) =>
		request<void>(`/v1/me/surveys/${sessionId}/answers`, { method: 'POST', body: { answers } }),
	complete: (sessionId: string) =>
		request<{ stage: Stage }>(`/v1/me/surveys/${sessionId}/complete`, { method: 'POST' }),
	deleteMe: () => request<void>('/v1/me', { method: 'DELETE' })
};

/** User-facing message for an API failure. */
export function apiErrorMessage(e: unknown): string {
	if (!(e instanceof ApiError)) return m.error_generic();
	if (e.status === 0) return m.error_network();
	if (e.status === 429) return m.error_busy();
	if (e.status === 503) return m.error_writes_disabled();
	return m.error_generic();
}

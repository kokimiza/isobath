import { PUBLIC_API_BASE } from '$env/static/public';
import { m } from '$lib/paraglide/messages.js';
import { supabase } from './supabase';

/** COLLECTING: no fitted chart yet. The API may still return a legacy 'UNCHARTED'. */
export type Stage = 'COLLECTING' | 'CHARTED' | 'UNCHARTED';

/** 95% credible region of the own position in map coordinates (statistics.md §6.3). */
export type CredibleRegion =
	| { kind: 'point'; center: number[]; mass: number }
	| { kind: 'segment'; endpoints: number[][]; mass: number }
	| {
			kind: 'grid_hpd';
			/** x edges, y edges (bins + 1 each) */
			edges: [number[], number[]];
			bins: number;
			/** smoothed posterior mass per cell, index = ix * bins + iy */
			cell_probability: number[];
			mass: number;
			probability: number;
	  };

/** Posterior placement shared by the current position and history snapshots. */
interface Placement {
	position?: number[];
	se?: number[];
	confidence?: number;
	credible_region?: CredibleRegion | null;
	/** probability of belonging to no displayed region */
	unmatched?: { alignment_unmatched: number; unseen: number; total: number } | null;
	/** joint: the answers were part of the fit; cut: placed against the fixed published chart */
	inference_mode?: 'joint' | 'cut' | null;
	regions?: { lineage_id: string; p: number }[];
	near_boundary?: boolean;
}
export type ConsentDocument = 'terms' | 'privacy' | 'research';
export type ConsentVersions = Record<ConsentDocument, string>;

export interface Meta {
	chart: { version: string; stage: Stage };
	participants: number;
	emergency_level: number;
	signup_enabled: boolean;
	survey_write_enabled: boolean;
	consent_versions: ConsentVersions;
	consent_required: ConsentDocument[];
	updated_at: string | null;
	next_update_at: string;
	stale: boolean;
}

export interface ConsentStatus {
	required: Partial<ConsentVersions>;
	versions: ConsentVersions;
	complete: boolean;
	research: boolean;
}

export interface Position extends Placement {
	chart: { version: string; stage: Stage };
	observer_no: number;
	participants: number;
	survey: {
		initial_completed: boolean;
		open_session: boolean;
		open_kind: 'initial' | 'continuous' | null;
		continuous_done_today: boolean;
	};
	/** last nightly update (cutoff) and the next one */
	updated_at: string | null;
	next_update_at: string;
}

/** Aggregated density grid produced by the nightly batch (no individual points). */
export interface ChartMap {
	bins: number;
	extent: [number, number, number, number];
	k: number;
	counts: number[][];
}

export interface ChartResponse {
	chart: { version: string; stage: Stage };
	updated_at: string | null;
	next_update_at: string;
	map: ChartMap;
}

export interface Snapshot extends Placement {
	id: number;
	chart: { version: string; stage: Stage };
	position: number[];
	se: number[];
	confidence: number;
	at: string;
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

interface ErrorBody {
	error?: { code?: string };
}

export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
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
	method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
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
			signal: AbortSignal.timeout(TIMEOUT_MS),
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
		const payload = (await res.json().catch(() => null)) as ErrorBody | null;
		throw new ApiError(res.status, payload?.error?.code ?? 'error');
	}
	return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
	meta: () => request<Meta>('/v1/meta', { auth: false }),
	position: () => request<Position>('/v1/me/position'),
	consents: () => request<ConsentStatus>('/v1/me/consents'),
	agree: (versions: Partial<ConsentVersions>) =>
		request<void>('/v1/me/consents', {
			method: 'POST',
			body: {
				consents: Object.entries(versions).map(([document, version]) => ({ document, version })),
			},
		}),
	createSurvey: (kind: SurveySummary['kind']) =>
		request<SurveySummary>('/v1/me/surveys', { method: 'POST', body: { kind } }),
	currentSurvey: () => request<SurveySummary & { questions: Question[] }>('/v1/me/surveys/current'),
	answer: (sessionId: string, answers: Answer[]) =>
		request<void>(`/v1/me/surveys/${sessionId}/answers`, { method: 'POST', body: { answers } }),
	complete: (sessionId: string) =>
		request<{ next_update_at: string }>(`/v1/me/surveys/${sessionId}/complete`, {
			method: 'POST',
		}),
	research: (participating: boolean) =>
		request<void>('/v1/me/research', { method: 'PUT', body: { participating } }),
	chart: () => request<ChartResponse>('/v1/chart/current', { auth: false }),
	history: (cursor?: number) =>
		request<{ items: Snapshot[]; next_cursor: number | null }>(
			`/v1/me/history?limit=50${cursor ? `&cursor=${cursor}` : ''}`,
		),
	deleteMe: () => request<void>('/v1/me', { method: 'DELETE' }),
};

/** User-facing message for an API failure. */
export function apiErrorMessage(e: unknown): string {
	if (!(e instanceof ApiError)) return m.error_generic();
	if (e.code === 'survey_not_ready') return m.error_survey_not_ready();
	if (e.status === 0) return m.error_network();
	if (e.status === 429) return m.error_busy();
	if (e.status === 503) return m.error_writes_disabled();
	return m.error_generic();
}

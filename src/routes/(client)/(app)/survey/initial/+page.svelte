<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, ApiError, type Answer, type Question } from '$lib/api.svelte';
	import { loadDraft, saveDraft } from '$lib/draft';
	import { href } from '$lib/nav';
	import LikertItem from '$lib/components/LikertItem.svelte';
	import { formatUpdateTime } from '$lib/i18n';

	const BATCH = 5; // FR-SUR-05: 5-10 answers per request
	const MAX_BATCH = 20; // API limit

	type Phase = 'loading' | 'answering' | 'completing' | 'done' | 'error';

	let phase = $state<Phase>('loading');
	let sessionId = '';
	let total = $state(0);
	let answeredOnServer = $state(0);
	let queue = $state<Question[]>([]);
	let pending = $state<Answer[]>([]);
	let syncing = $state(false);
	let syncError = $state<string | null>(null);
	let error = $state<string | null>(null);
	let shownAt = 0;
	let nextUpdateAt = $state('');

	const current = $derived(queue[0]);
	const answered = $derived(answeredOnServer + pending.length);

	onMount(async () => {
		try {
			const session = await api.createSurvey('initial'); // returns the open one if it exists
			sessionId = session.id;
			total = session.total;
			answeredOnServer = session.answered;
			pending = loadDraft(sessionId);
			await sync(true);
			if (!syncError) await nextPage();
			else phase = 'answering';
		} catch (e) {
			if (e instanceof ApiError && e.code === 'initial_exists') {
				await goto(href('/profile'), { replaceState: true });
				return;
			}
			fail(e);
		}
	});

	$effect(() => {
		if (current) shownAt = performance.now(); // FR-SUR-09, client-reported (ST-QLT-06)
	});

	function fail(e: unknown) {
		error = apiErrorMessage(e);
		phase = 'error';
	}

	async function nextPage() {
		const cur = await api.currentSurvey();
		queue = cur.questions;
		if (queue.length === 0) await complete();
		else phase = 'answering';
	}

	/**
	 * Single sender. Sends while a batch is full, the page is exhausted, or `force`;
	 * conditions are re-checked after every request so answers given meanwhile are included.
	 */
	async function sync(force = false) {
		if (syncing) return;
		syncing = true;
		try {
			while (
				!syncError &&
				pending.length > 0 &&
				(force || pending.length >= BATCH || queue.length === 0)
			) {
				await send(pending.slice(0, MAX_BATCH));
			}
		} finally {
			syncing = false;
		}
		if (phase === 'answering' && !syncError && pending.length === 0 && queue.length === 0) {
			await nextPage();
		}
	}

	async function send(batch: Answer[]) {
		try {
			await api.answer(sessionId, batch);
			pending = pending.slice(batch.length);
			answeredOnServer += batch.length;
		} catch (e) {
			if (!(e instanceof ApiError && e.code === 'already_answered')) {
				syncError = apiErrorMessage(e);
				return;
			}
			// an earlier request reached the server but its response was lost: keep only unsaved ones
			const cur = await api.currentSurvey();
			const open = new Set(cur.questions.map((q) => q.id));
			pending = pending.filter((a) => open.has(a.question_id));
			answeredOnServer = cur.answered;
		} finally {
			saveDraft(sessionId, pending);
		}
	}

	function answer(value: number) {
		if (!current || phase !== 'answering') return;
		pending = [
			...pending,
			{ question_id: current.id, value, response_ms: Math.round(performance.now() - shownAt) },
		];
		saveDraft(sessionId, pending);
		queue = queue.slice(1);
		sync().catch(fail);
	}

	function retry() {
		syncError = null;
		sync(true).catch(fail);
	}

	async function complete() {
		phase = 'completing';
		// nothing is recomputed now: the nightly update reflects it (requirements §4.1)
		nextUpdateAt = (await api.complete(sessionId)).next_update_at;
		phase = 'done';
	}

	function onkeydown(event: KeyboardEvent) {
		const value = Number(event.key);
		if (value >= 1 && value <= 5 && !event.repeat) answer(value);
	}

	// flush on tab hide / close so a draft is rarely needed
	function onvisibilitychange() {
		if (document.visibilityState === 'hidden') sync(true).catch(() => undefined); // unsent answers stay in the draft
	}
</script>

<svelte:window {onkeydown} />
<svelte:document {onvisibilitychange} />

<h1 class="text-2xl font-semibold">{m.survey_initial_title()}</h1>

{#if phase === 'loading'}
	<p role="status" class="mt-6 text-slate-400">{m.common_loading()}</p>
{:else if phase === 'error'}
	<p class="mt-6 alert" role="alert">{error}</p>
{:else if phase === 'completing'}
	<p role="status" class="mt-6 text-slate-400">{m.survey_completing()}</p>
{:else if phase === 'done'}
	<section class="mt-6 space-y-4 rounded-lg border border-cyan-800 p-5" role="status">
		<h2 class="font-semibold text-cyan-300">{m.survey_done_title()}</h2>
		<p class="text-sm leading-relaxed text-slate-300">
			{m.survey_done_body({ time: formatUpdateTime(nextUpdateAt) })}
		</p>
		<a href={href('/profile')} class="btn-primary">{m.survey_done_to_profile()}</a>
	</section>
{:else}
	<div class="mt-6">
		<div class="flex justify-between text-sm text-slate-400">
			<span>{m.survey_progress_label()}</span>
			<span>{m.survey_progress({ answered, total })}</span>
		</div>
		<progress class="mt-2 h-1 w-full accent-cyan-400" max={total} value={answered}></progress>
	</div>

	{#if current}
		{#key current.id}
			<div class="mt-10">
				<LikertItem text={current.text} onanswer={answer} />
			</div>
		{/key}
		<p class="mt-6 text-xs text-slate-500">{m.survey_keyboard_hint()}</p>
	{:else}
		<p role="status" class="mt-10 text-slate-400">{m.survey_saving()}</p>
	{/if}

	{#if syncError}
		<div class="mt-6 flex items-center justify-between gap-4 alert" role="alert">
			<span>{m.survey_sync_failed()} {syncError}</span>
			<button type="button" class="btn-secondary shrink-0" onclick={retry} disabled={syncing}>
				{m.survey_retry()}
			</button>
		</div>
	{/if}
{/if}

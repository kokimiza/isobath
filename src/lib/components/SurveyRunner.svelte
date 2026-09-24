<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { m } from '$lib/paraglide/messages.js';
	import {
		api,
		apiErrorMessage,
		ApiError,
		type Answer,
		type Question,
		type SurveySummary,
	} from '$lib/api.svelte';
	import { loadDraft, saveDraft } from '$lib/draft';
	import { formatUpdateTime } from '$lib/i18n';
	import { href } from '$lib/nav';
	import LikertItem from '$lib/components/LikertItem.svelte';

	let { kind, title }: { kind: SurveySummary['kind']; title: string } = $props();

	const BATCH = 5; // FR-SUR-05: 5-10 answers per request
	const MAX_BATCH = 20; // API limit

	type Phase = 'loading' | 'answering' | 'completing' | 'done' | 'unavailable' | 'error';

	let phase = $state<Phase>('loading');
	let sessionId = '';
	let total = $state(0);
	let answeredOnServer = $state(0);
	let queue = $state<Question[]>([]);
	let pending = $state<Answer[]>([]);
	let syncing = $state(false);
	let syncError = $state<string | null>(null);
	let error = $state<string | null>(null);
	let unavailable = $state('');
	let shownAt = 0;
	let nextUpdateAt = $state('');
 let active = true;
 const reads = new AbortController();
 let inFlight: Promise<void> | null = null;
 let flushRequested = false;
 let starting = $state(false);
 let completionRequested = false;
 let storageError = $state(false);
 onDestroy(() => { active = false; reads.abort(); });
 function persist() { storageError = !saveDraft(sessionId, pending); }


	const current = $derived(queue[0]);
	const answered = $derived(answeredOnServer + pending.length);

 onMount(() => { void initialize(); });
 async function initialize() {
  if (starting || !active) return;
  starting = true;
  error = null;
  phase = 'loading';
  try {
   const session = await api.createSurvey(kind);
   if (!active) return;
   sessionId = session.id;
   total = session.total;
   answeredOnServer = session.answered;
   pending = loadDraft(sessionId);
   await sync(true);
  } catch (e) { if (active) await refuse(e); }
  finally { if (active) starting = false; }
 }

	/** Server refused to open a session: redirect or explain instead of a generic error. */
	async function refuse(e: unknown) {
		if (!active) return;
		if (!(e instanceof ApiError)) return fail(e);
		switch (e.code) {
			case 'survey_not_ready':
				unavailable = m.error_survey_not_ready();
				phase = 'unavailable';
				return;
			case 'initial_exists':
				return goto(href('/profile'), { replaceState: true });
			case 'initial_required':
				return goto(href('/survey/initial'), { replaceState: true });
			case 'too_soon': {
				// one continuous survey per nightly window (FR-CON-05)
				const meta = await api.meta(reads.signal).catch(() => null);
				if (!active) return;
				unavailable = meta
					? m.survey_continuous_done_today({ time: formatUpdateTime(meta.next_update_at) })
					: m.survey_continuous_done_today_plain();
				phase = 'unavailable';
				return;
			}
			case 'nothing_to_ask':
				unavailable = m.survey_nothing_to_ask();
				phase = 'unavailable';
				return;
			default:
				return fail(e);
		}
	}

	$effect(() => {
		if (current) shownAt = performance.now(); // FR-SUR-09, client-reported (ST-QLT-06)
	});

	function fail(e: unknown) {
		if (!active) return;
		error = apiErrorMessage(e);
		phase = 'error';
	}

	async function nextPage() {
		const cur = await api.currentSurvey(reads.signal);
		if (!active) return;
		if (cur.id !== sessionId) throw new ApiError(409, 'session_closed');
		queue = cur.questions;
		if (queue.length === 0) await complete();
		else phase = 'answering';
	}

	/**
	 * Single sender. Sends while a batch is full, the page is exhausted, or `force`;
	 * conditions are re-checked after every request so answers given meanwhile are included.
	 */
 function sync(force = false): Promise<void> {
  if (!active || phase === 'done' || phase === 'unavailable') return Promise.resolve();
  flushRequested ||= force;
  if (inFlight) return inFlight;
  syncing = true;
  inFlight = (async () => {
   if (completionRequested) { await complete(); return; }
   while (active && !syncError && pending.length > 0 && (flushRequested || pending.length >= BATCH || queue.length === 0)) {
    await send(pending.slice(0, MAX_BATCH));
   }
   if (!active) return;
   if (syncError) { phase = 'answering'; return; }
   if (pending.length === 0 && queue.length === 0) await nextPage();
  })().finally(() => {
   inFlight = null;
   flushRequested = false;
   if (active) syncing = false;
  });
  return inFlight;
 }

	async function send(batch: Answer[]) {
		try {
			await api.answer(sessionId, batch);
			if (!active) return;
			pending = pending.slice(batch.length);
			answeredOnServer += batch.length;
		} catch (e) {
			if (!active) return;
			if (!(e instanceof ApiError && e.code === 'already_answered')) {
				syncError = apiErrorMessage(e);
				return;
			}
			// an earlier request reached the server but its response was lost: keep only unsaved ones
			const cur = await api.currentSurvey(reads.signal);
		if (!active) return;
			const open = new Set(cur.questions.map((q) => q.id));
			pending = pending.filter((a) => open.has(a.question_id));
			answeredOnServer = cur.answered;
		} finally {
			if (active) persist();
		}
	}

	function answer(value: number) {
		if (!current || phase !== 'answering') return;
		pending = [
			...pending,
			{ question_id: current.id, value, response_ms: Math.round(performance.now() - shownAt) },
		];
		if (active) persist();
		queue = queue.slice(1);
		sync(storageError).catch(fail);
	}

	function retry() {
  if (syncing || starting || !active) return;
  error = null;
  syncError = null;
  if (!sessionId) { void initialize(); return; }
  phase = 'answering';
  void sync(true).catch(fail);
 }

	async function complete() {
		if (!active) return;
		completionRequested = true;
		phase = 'completing';
		// nothing is recomputed now: the nightly update reflects it (requirements §4.1)
		const result = await api.complete(sessionId);
		if (!active) return;
		nextUpdateAt = result.next_update_at;
		phase = 'done';
	}

	function onkeydown(event: KeyboardEvent) {
		const value = Number(event.key);
		if (value >= 1 && value <= 5 && !event.repeat) answer(value);
	}

	// flush on tab hide / close so a draft is rarely needed
	function onvisibilitychange() {
		if (document.visibilityState === 'hidden') sync(true).catch(fail); // unsent answers stay in the draft
	}
</script>

<svelte:window {onkeydown} />
<svelte:document {onvisibilitychange} />

<h1 class="text-2xl font-semibold">{title}</h1>
<p class="mt-2 text-sm text-muted">{m.survey_rest_note()}</p>
{#if storageError && pending.length}<p role="alert" class="mt-4 text-sm text-warning">{m.survey_storage_unavailable()}</p>{/if}

{#if phase === 'loading'}
	<p role="status" class="mt-6 text-muted">{m.common_loading()}</p>
{:else if phase === 'error'}
	<p class="mt-6 alert" role="alert">{error}</p>
	<button type="button" class="mt-4 btn-secondary" onclick={retry} disabled={syncing || starting}>{m.survey_retry()}</button>
{:else if phase === 'unavailable'}
	<section class="mt-6 space-y-4 rounded-lg border border-line p-5" role="status">
		<p class="text-sm leading-relaxed text-body">{unavailable}</p>
		<a href={href('/profile')} class="btn-secondary">{m.survey_done_to_profile()}</a>
	</section>
{:else if phase === 'completing'}
	<p role="status" class="mt-6 text-muted">{m.survey_completing()}</p>
{:else if phase === 'done'}
	<section class="mt-6 space-y-4 rounded-lg border border-line p-5" role="status">
		<h2 class="font-semibold text-ocean">{m.survey_done_title()}</h2>
		<p class="text-sm leading-relaxed text-body">
			{m.survey_done_body({ time: formatUpdateTime(nextUpdateAt) })}
		</p>
		<a href={href('/profile')} class="btn-primary">{m.survey_done_to_profile()}</a>
	</section>
{:else}
	<div class="mt-6">
		<div class="flex justify-between text-sm text-muted">
			<span>{m.survey_progress_label()}</span>
			<span>{m.survey_progress({ answered, total })}</span>
		</div>
		<progress
			aria-label={m.survey_progress_label()}
			class="mt-3 h-1.5 w-full accent-ocean"
			max={total}
			value={answered}
		></progress>
	</div>

	{#if current}
		{#key current.id}
			<div class="mt-10">
				<LikertItem text={current.text} onanswer={answer} />
			</div>
		{/key}
		<p class="mt-6 text-xs text-muted">{m.survey_keyboard_hint()}</p>
	{:else}
		<p role="status" class="mt-10 text-muted">{m.survey_saving()}</p>
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

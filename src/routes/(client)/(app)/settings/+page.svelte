<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage } from '$lib/api.svelte';
	import { clearDrafts } from '$lib/draft';
	import { href } from '$lib/nav';
	import { supabase } from '$lib/supabase';

	let research = $state<boolean | null>(null);
	let researchBusy = $state(false);
	let confirming = $state(false);
	let busy = $state(false);
	let error = $state<string | null>(null);

	onMount(() => {
		api
			.consents()
			.then((s) => (research = s.research))
			.catch((e) => (error = apiErrorMessage(e)));
	});

	async function setResearch(participating: boolean) {
		researchBusy = true;
		try {
			await api.research(participating);
			research = participating;
		} catch (e) {
			error = apiErrorMessage(e);
		} finally {
			researchBusy = false;
		}
	}

	async function logout() {
		clearDrafts();
		await supabase().auth.signOut();
		await goto(href('/'));
	}

	async function deleteAccount() {
		if (!confirming) {
			confirming = true;
			return;
		}
		busy = true;
		try {
			await api.deleteMe();
			clearDrafts();
			// the user no longer exists server-side; just drop the local session
			await supabase().auth.signOut({ scope: 'local' });
			await goto(href('/'));
		} catch (e) {
			error = apiErrorMessage(e);
			busy = false;
		}
	}
</script>

<h1 class="text-2xl font-semibold">{m.settings_title()}</h1>

<section class="mt-8 space-y-3">
	<h2 class="text-sm text-slate-400">{m.settings_account()}</h2>
	<button type="button" class="btn-secondary" onclick={logout}>{m.settings_logout()}</button>
</section>

<section class="mt-10 space-y-3 rounded-lg border border-slate-800 p-5">
	<h2 class="font-semibold">{m.settings_research_title()}</h2>
	{#if research !== null}
		<p class="text-sm text-slate-300">
			{research ? m.settings_research_on() : m.settings_research_off()}
		</p>
		<p class="text-xs text-slate-400">{m.settings_research_note()}</p>
		<button
			type="button"
			class={research ? 'btn-secondary' : 'btn-primary'}
			onclick={() => setResearch(!research)}
			disabled={researchBusy}
		>
			{research ? m.settings_research_withdraw() : m.settings_research_join()}
		</button>
	{/if}
</section>

<section class="mt-10 space-y-3 rounded-lg border border-rose-900 p-5">
	<h2 class="font-semibold text-rose-300">{m.settings_delete_title()}</h2>
	<p class="text-sm text-slate-300">{m.settings_delete_body()}</p>
	{#if confirming}
		<p class="text-sm font-semibold text-rose-300" role="alert">{m.settings_delete_confirm()}</p>
	{/if}
	{#if error}
		<p class="alert" role="alert">{error}</p>
	{/if}
	<button type="button" class="btn-danger" onclick={deleteAccount} disabled={busy}>
		{m.settings_delete_submit()}
	</button>
</section>

<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage } from '$lib/api.svelte';
	import { href } from '$lib/nav';
	import { supabase } from '$lib/supabase';

	let confirming = $state(false);
	let busy = $state(false);
	let error = $state<string | null>(null);

	async function logout() {
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

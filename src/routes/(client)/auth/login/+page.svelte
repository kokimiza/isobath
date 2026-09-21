<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { DEV_LOGIN_IDS, loginEmail, safeNext } from '$lib/auth.svelte';
	import { authErrorMessage } from '$lib/i18n';
	import { href } from '$lib/nav';
	import { supabase } from '$lib/supabase';

	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		const { error: authError } = await supabase().auth.signInWithPassword({
			email: loginEmail(email),
			password,
		});
		busy = false;
		if (authError) {
			error = authErrorMessage(authError);
			return;
		}
		await goto(safeNext(page.url.searchParams.get('next')) ?? href('/profile'));
	}
</script>

<h1 class="text-2xl font-semibold">{m.login_title()}</h1>

<form class="mt-6 max-w-sm space-y-4" onsubmit={submit}>
	<label class="block text-sm">
		{m.auth_email()}
		<input
			class="field"
			type={DEV_LOGIN_IDS ? 'text' : 'email'}
			autocomplete="username"
			required
			bind:value={email}
		/>
	</label>
	<label class="block text-sm">
		{m.auth_password()}
		<input
			class="field"
			type="password"
			autocomplete="current-password"
			required
			bind:value={password}
		/>
	</label>
	{#if error}
		<p class="alert" role="alert">{error}</p>
	{/if}
	<button type="submit" class="btn-primary w-full" disabled={busy}>{m.login_submit()}</button>
</form>

<p class="mt-6 text-sm text-slate-400">
	{m.login_no_account()}
	<a href={href('/auth/signup')} class="text-cyan-300 underline">{m.login_to_signup()}</a>
</p>

<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, type ConsentVersions } from '$lib/api.svelte';
	import { MIN_PASSWORD_LENGTH } from '$lib/auth.svelte';
	import { authErrorMessage } from '$lib/i18n';
	import { href } from '$lib/nav';
	import { supabase } from '$lib/supabase';
	import ConsentFields, { consentItems } from '$lib/components/ConsentFields.svelte';

	let email = $state('');
	let password = $state('');
	let consent = $state(consentItems.map(() => false));
	const agreed = $derived(consent.every(Boolean));
	let versions = $state<ConsentVersions | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let sentTo = $state<string | null>(null);

	// Consent versions come from the API so exactly what was shown is what gets recorded.
	onMount(() => {
		api
			.meta()
			.then((meta) => (versions = meta.consent_versions))
			.catch((e) => (error = apiErrorMessage(e)));
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!versions || !agreed) return;
		busy = true;
		error = null;
		const { error: authError } = await supabase().auth.signUp({
			email,
			password,
			options: {
				emailRedirectTo: new URL(href('/auth/callback'), location.origin).href,
				// recorded server-side on first login (SEC-CON-01)
				data: { consents: versions }
			}
		});
		busy = false;
		if (authError) error = authErrorMessage(authError);
		else sentTo = email;
	}
</script>

<h1 class="text-2xl font-semibold">{m.signup_title()}</h1>

{#if sentTo}
	<section class="mt-6 rounded-lg border border-cyan-800 p-5" role="status">
		<h2 class="font-semibold text-cyan-300">{m.signup_sent_title()}</h2>
		<p class="mt-2 text-slate-300">{m.signup_sent_body({ email: sentTo })}</p>
	</section>
{:else}
	<p class="mt-2 text-slate-300">{m.signup_lead()}</p>

	<form class="mt-6 max-w-sm space-y-4" onsubmit={submit}>
		<label class="block text-sm">
			{m.auth_email()}
			<input class="field" type="email" autocomplete="email" required bind:value={email} />
		</label>
		<label class="block text-sm">
			{m.auth_password()}
			<input
				class="field"
				type="password"
				autocomplete="new-password"
				minlength={MIN_PASSWORD_LENGTH}
				required
				bind:value={password}
			/>
			<span class="mt-1 block text-xs text-slate-500">
				{m.auth_password_hint({ min: MIN_PASSWORD_LENGTH })}
			</span>
		</label>

		<ConsentFields bind:checked={consent} />

		{#if error}
			<p class="alert" role="alert">{error}</p>
		{/if}
		<button class="btn-primary w-full" disabled={busy || !agreed || !versions}>
			{m.signup_submit()}
		</button>
	</form>

	<p class="mt-6 text-sm text-slate-400">
		{m.signup_have_account()}
		<a href={href('/auth/login')} class="text-cyan-300 underline">{m.signup_to_login()}</a>
	</p>
{/if}

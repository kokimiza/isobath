<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, type ConsentVersions } from '$lib/api.svelte';
	import { MIN_PASSWORD_LENGTH, safeNext } from '$lib/auth.svelte';
	import { authErrorMessage } from '$lib/i18n';
	import { href } from '$lib/nav';
	import { supabase } from '$lib/supabase';
	import ConsentFields, {
		consentItems,
		consentSelection,
	} from '$lib/components/ConsentFields.svelte';

	let email = $state('');
	let password = $state('');
	let consent = $state(consentItems.map(() => false));
	let versions = $state<ConsentVersions | null>(null);
	const selection = $derived(versions ? consentSelection(consent, versions) : null);
	const agreed = $derived(selection?.ok ?? false);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let sentTo = $state<string | null>(null);
	const next = $derived(safeNext(page.url.searchParams.get('next')) ?? href('/survey'));

	// Consent versions come from the API so exactly what was shown is what gets recorded.
	onMount(() => {
		api
			.meta()
			.then((meta) => (versions = meta.consent_versions))
			.catch((e) => (error = apiErrorMessage(e)));
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!selection?.ok) return;
		busy = true;
		error = null;
		try {
			const { data, error: authError } = await supabase().auth.signUp({
				email,
				password,
				options: {
					emailRedirectTo: new URL(href('/auth/callback', { next }), location.origin).href,
					// recorded server-side on first login (SEC-CON-01)
					data: { consents: selection.agreed },
				},
			});
			if (authError) error = authErrorMessage(authError);
			else if (data.session) await goto(next);
			else sentTo = email;
		} catch {
			error = m.auth_error_generic();
		} finally {
			busy = false;
		}
	}
</script>

<h1 class="text-2xl font-semibold">{m.signup_title()}</h1>

{#if sentTo}
	<section class="mt-6 rounded-lg border border-line p-5" role="status">
		<h2 class="font-semibold text-ocean">{m.signup_sent_title()}</h2>
		<p class="mt-2 text-body">{m.signup_sent_body({ email: sentTo })}</p>
	</section>
{:else}
	<p class="mt-2 text-body">{m.signup_lead()}</p>

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
			<span class="mt-1 block text-xs text-muted">
				{m.auth_password_hint({ min: MIN_PASSWORD_LENGTH })}
			</span>
		</label>

		<ConsentFields bind:checked={consent} />

		{#if error}
			<p class="alert" role="alert">{error}</p>
		{/if}
		<button type="submit" class="btn-primary w-full" disabled={busy || !agreed || !versions}>
			{m.signup_submit()}
		</button>
	</form>

	<p class="mt-6 text-sm text-muted">
		{m.signup_have_account()}
		<a href={href('/auth/login', { next })} class="text-ocean underline">{m.signup_to_login()}</a>
	</p>
{/if}

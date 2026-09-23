<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '$lib/paraglide/messages.js';
	import { MIN_PASSWORD_LENGTH, DEV_LOGIN_IDS, loginEmail } from '$lib/auth.svelte';
	import { authErrorMessage } from '$lib/i18n';
	import { href } from '$lib/nav';
	import { supabase } from '$lib/supabase';
	let { mode, next }: { mode: 'signup' | 'login'; next: string } = $props();
	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);
	let sentTo = $state<string | null>(null);
	async function google() {
		busy = true;
		error = null;
		try {
			const result = await supabase().auth.signInWithOAuth({
				provider: 'google',
				options: { redirectTo: new URL(href('/auth/callback', { next }), location.origin).href },
			});
			if (result.error) {
				error = authErrorMessage(result.error);
				busy = false;
			}
		} catch {
			error = m.auth_error_generic();
			busy = false;
		}
	}
	async function submit(event: SubmitEvent) {
		event.preventDefault();
		busy = true;
		error = null;
		try {
			const result =
				mode === 'signup'
					? await supabase().auth.signUp({
							email,
							password,
							options: {
								emailRedirectTo: new URL(href('/auth/callback', { next }), location.origin).href,
							},
						})
					: await supabase().auth.signInWithPassword({ email: loginEmail(email), password });
			if (result.error) error = authErrorMessage(result.error);
			else if (result.data.session) await goto(next);
			else sentTo = email;
		} catch {
			error = m.auth_error_generic();
		} finally {
			busy = false;
		}
	}
</script>

{#if sentTo}
	<section class="mt-6 rounded-lg border border-line p-5" role="status">
		<h2 class="font-semibold text-ocean">{m.signup_sent_title()}</h2>
		<p class="mt-2 text-body">{m.signup_sent_body({ email: sentTo })}</p>
	</section>
{:else}
	<div class="mt-6 max-w-md space-y-5">
		<button type="button" class="btn-primary w-full" disabled={busy} onclick={google}
			>{mode === 'signup' ? m.signup_google() : m.login_google()}</button
		>
		<p class="text-sm text-muted">{m.auth_google_return()}</p>
		<details class="border-t border-line pt-5">
			<summary class="cursor-pointer text-sm text-ocean">{m.auth_email_alternative()}</summary>
			<form class="mt-5 space-y-4" onsubmit={submit}>
				<label class="block text-sm"
					>{m.auth_email()}<input
						class="field"
						type={mode === 'login' && DEV_LOGIN_IDS ? 'text' : 'email'}
						autocomplete="username"
						required
						bind:value={email}
					/></label
				>
				<label class="block text-sm"
					>{m.auth_password()}<input
						class="field"
						type="password"
						autocomplete={mode === 'signup' ? 'new-password' : 'current-password'}
						minlength={mode === 'signup' ? MIN_PASSWORD_LENGTH : undefined}
						required
						bind:value={password}
					/></label
				>
				{#if mode === 'signup'}<p class="text-xs text-muted">
						{m.auth_password_hint({ min: MIN_PASSWORD_LENGTH })}
					</p>{/if}
				<button type="submit" class="btn-secondary w-full" disabled={busy}
					>{mode === 'signup' ? m.signup_submit() : m.login_submit()}</button
				>
			</form>
		</details>
		{#if error}<p class="alert" role="alert">{error}</p>{/if}
	</div>
{/if}

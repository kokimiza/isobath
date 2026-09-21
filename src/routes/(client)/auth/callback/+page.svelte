<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';
	import { supabase } from '$lib/supabase';

	let failed = $state(false);

	// PKCE: the email link returns ?code=..., exchanged with the verifier stored at signup.
	onMount(async () => {
		const code = page.url.searchParams.get('code');
		const { error } = code ? await supabase().auth.exchangeCodeForSession(code) : { error: true };
		if (error) failed = true;
		else await goto(href('/profile'), { replaceState: true });
	});
</script>

{#if failed}
	<p class="alert" role="alert">{m.callback_failed()}</p>
	<a href={href('/auth/login')} class="mt-6 btn-secondary">{m.nav_login()}</a>
{:else}
	<p role="status" class="text-slate-400">{m.callback_processing()}</p>
{/if}

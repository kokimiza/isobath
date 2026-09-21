<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { apiErrorMessage } from '$lib/api.svelte';
	import { ensureConsent } from '$lib/consent';
	import { href } from '$lib/nav';

	let { children, data } = $props();

	const CONSENT_ROUTE = '/(client)/(app)/consent';
	let ready = $state(false);
	let error = $state<string | null>(null);

	onMount(async () => {
		if (page.route.id === CONSENT_ROUTE) {
			ready = true;
			return;
		}
		try {
			if (await ensureConsent(data.session)) ready = true;
			else await goto(href('/consent', { next: page.url.pathname }), { replaceState: true });
		} catch (e) {
			error = apiErrorMessage(e);
		}
	});
</script>

{#if error}
	<p class="alert" role="alert">{error}</p>
{:else if ready}
	{@render children()}
{:else}
	<p role="status" class="text-slate-400">{m.common_loading()}</p>
{/if}

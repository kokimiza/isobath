<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, type ConsentVersions } from '$lib/api.svelte';
	import { safeNext } from '$lib/auth.svelte';
	import { markConsented } from '$lib/consent';
	import { href } from '$lib/nav';
	import ConsentFields, { consentItems } from '$lib/components/ConsentFields.svelte';

	let { data } = $props();

	let consent = $state(consentItems.map(() => false));
	const agreed = $derived(consent.every(Boolean));
	let versions = $state<ConsentVersions | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);

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
		try {
			await api.agree(versions);
			markConsented(data.session);
			await goto(safeNext(page.url.searchParams.get('next')) ?? href('/profile'));
		} catch (e) {
			error = apiErrorMessage(e);
		} finally {
			busy = false;
		}
	}
</script>

<h1 class="text-2xl font-semibold">{m.consent_title()}</h1>
<p class="mt-2 text-slate-300">{m.consent_lead()}</p>

<form class="mt-6 max-w-md space-y-4" onsubmit={submit}>
	<ConsentFields bind:checked={consent} />
	{#if error}
		<p class="alert" role="alert">{error}</p>
	{/if}
	<button type="submit" class="btn-primary" disabled={busy || !agreed || !versions}
		>{m.consent_submit()}</button
	>
</form>

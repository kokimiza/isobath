<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, type ConsentVersions } from '$lib/api.svelte';
	import { safeNext } from '$lib/auth.svelte';
	import { markConsented } from '$lib/consent';
	import { href } from '$lib/nav';
	import ConsentFields, {
		consentItems,
		consentSelection,
	} from '$lib/components/ConsentFields.svelte';

	let { data } = $props();

	let consent = $state(consentItems.map(() => false));
	let versions = $state<ConsentVersions | null>(null);
	const selection = $derived(versions ? consentSelection(consent, versions) : null);
	const agreed = $derived(selection?.ok ?? false);
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
		if (!selection?.ok) return;
		busy = true;
		error = null;
		try {
			await api.agree(selection.agreed);
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
<p class="mt-2 text-body">{m.consent_lead()}</p>

<form class="mt-6 max-w-md space-y-4" onsubmit={submit}>
	<ConsentFields bind:checked={consent} />
	{#if error}
		<p class="alert" role="alert">{error}</p>
	{/if}
	<button type="submit" class="btn-primary" disabled={busy || !agreed || !versions}
		>{m.consent_submit()}</button
	>
</form>

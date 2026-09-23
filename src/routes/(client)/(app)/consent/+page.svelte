<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import {
		api,
		apiErrorMessage,
		type ConsentVersions,
		type ConsentDocument,
		type Registration,
	} from '$lib/api.svelte';
	import DemographicFields from '$lib/components/DemographicFields.svelte';
	import { clearRegistration, loadRegistration, validDemographics } from '$lib/registration';
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
	let pending = $state<boolean | null>(null);
	let birthYear = $state<number | undefined>();
	let birthMonth = $state('');
	let gender = $state('');

	onMount(() => {
		api
			.consents()
			.then((status) => {
				versions = status.versions;
				pending = status.registration_required;
				const draft = loadRegistration();
				if (pending && draft) {
					birthYear = draft.birth_year;
					birthMonth = String(draft.birth_month);
					gender = draft.gender;
				}
			})
			.catch((e) => (error = apiErrorMessage(e)));
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!selection?.ok) return;
		if (pending && !validDemographics(birthYear, birthMonth, gender)) {
			error = m.signup_demographics_invalid();
			return;
		}
		busy = true;
		error = null;
		try {
			if (pending) {
				await api.completeRegistration({
					birth_year: birthYear!,
					birth_month: Number(birthMonth),
					gender: gender as Registration['gender'],
					adult_confirmed: true,
					non_diagnostic_confirmed: true,
					consents: Object.entries(selection.agreed).map(([document, version]) => ({
						document: document as ConsentDocument,
						version,
					})),
				});
			} else await api.agree(selection.agreed);
			clearRegistration();
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
	{#if pending}
		<p class="text-sm text-body">{m.registration_recover()}</p>
		<DemographicFields bind:birthYear bind:birthMonth bind:gender />
	{/if}
	<ConsentFields bind:checked={consent} />
	{#if error}
		<p class="alert" role="alert">{error}</p>
	{/if}
	<button
		type="submit"
		class="btn-primary"
		disabled={busy || !agreed || !versions || pending === null}>{m.consent_submit()}</button
	>
</form>

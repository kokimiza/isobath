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
	import { safeNext } from '$lib/auth.svelte';
	import { href } from '$lib/nav';
	import { loadRegistration, saveRegistration, validDemographics } from '$lib/registration';
	import DemographicFields from '$lib/components/DemographicFields.svelte';
	import ConsentFields, {
		consentItems,
		consentSelection,
	} from '$lib/components/ConsentFields.svelte';

	let birthYear = $state<number | undefined>();
	let birthMonth = $state('');
	let gender = $state('');
	let consent = $state(consentItems.map(() => false));
	let versions = $state<ConsentVersions | null>(null);
	let error = $state<string | null>(null);
	const selection = $derived(versions ? consentSelection(consent, versions) : null);
	const next = $derived(safeNext(page.url.searchParams.get('next')) ?? href('/survey'));
	onMount(async () => {
		try {
			versions = (await api.meta()).consent_versions;
			const draft = loadRegistration();
			if (draft) {
				birthYear = draft.birth_year;
				birthMonth = String(draft.birth_month);
				gender = draft.gender;
				consent = consentItems.map((item) =>
					item.document
						? draft.consents.some(
								(c) => c.document === item.document && c.version === versions?.[item.document],
							)
						: true,
				);
			}
		} catch (e) {
			error = apiErrorMessage(e);
		}
	});
	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!selection?.ok) return;
		if (!validDemographics(birthYear, birthMonth, gender)) {
			error = m.signup_demographics_invalid();
			return;
		}
		try {
			saveRegistration({
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
			await goto(href('/auth/register', { next }));
		} catch {
			error = m.signup_draft_unavailable();
		}
	}
</script>

<h1 class="text-2xl font-semibold">{m.signup_title()}</h1>
<p class="mt-2 max-w-md text-body">{m.signup_prepare_lead()}</p>
<form class="mt-6 max-w-md space-y-5" onsubmit={submit}>
	<DemographicFields bind:birthYear bind:birthMonth bind:gender />
	<ConsentFields bind:checked={consent} />
	{#if error}<p class="alert" role="alert">{error}</p>{/if}
	<button type="submit" class="btn-primary w-full" disabled={!selection?.ok || !versions}
		>{m.signup_continue()}</button
	>
</form>
<p class="mt-6 text-sm text-muted">
	{m.signup_have_account()}
	<a href={href('/auth/login', { next })} class="text-ocean underline">{m.signup_to_login()}</a>
</p>

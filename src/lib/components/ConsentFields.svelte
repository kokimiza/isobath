<script lang="ts" module>
	import type { Pathname } from '$app/types';
	import type { ConsentDocument, ConsentVersions } from '$lib/api.svelte';
	import { m } from '$lib/paraglide/messages.js';

	interface ConsentItem {
		label: () => string;
		doc?: Pathname;
		/** recorded as a consent event when checked */
		document?: ConsentDocument;
		required: boolean;
	}

	export const consentItems: ConsentItem[] = [
		{ label: m.consent_terms, doc: '/legal/terms', document: 'terms', required: true },
		{ label: m.consent_privacy, doc: '/legal/privacy', document: 'privacy', required: true },
		{ label: m.consent_adult, required: true },
		{ label: m.consent_non_diagnostic, required: true },
		{ label: m.consent_research, doc: '/legal/research', document: 'research', required: false },
	];

	/** Required boxes all checked, and the document versions to record. */
	export function consentSelection(checked: boolean[], versions: ConsentVersions) {
		const ok = consentItems.every((item, i) => !item.required || checked[i]);
		const agreed: Partial<ConsentVersions> = {};
		consentItems.forEach((item, i) => {
			if (item.document && checked[i]) agreed[item.document] = versions[item.document];
		});
		return { ok, agreed };
	}
</script>

<script lang="ts">
	import { href } from '$lib/nav';

	let { checked = $bindable() }: { checked: boolean[] } = $props();
</script>

{#snippet item(entry: ConsentItem, i: number)}
	<div class="flex items-start gap-2">
		<input
			id="consent-{i}"
			type="checkbox"
			class="mt-0.5 rounded border-line bg-mist text-ocean focus:ring-ocean"
			required={entry.required}
			bind:checked={checked[i]}
		/>
		<label for="consent-{i}">
			{entry.label()}
			{#if entry.doc}
				<a
					href={href(entry.doc)}
					target="_blank"
					rel="noopener noreferrer"
					class="text-ocean underline"
				>
					{m.legal_read()}
				</a>
			{/if}
		</label>
	</div>
{/snippet}

<fieldset class="space-y-2 text-sm">
	<legend class="mb-2 text-xs text-muted">{m.consent_required_heading()}</legend>
	{#each consentItems as entry, i (i)}
		{#if entry.required}{@render item(entry, i)}{/if}
	{/each}
</fieldset>

<fieldset class="mt-4 space-y-2 rounded-md border border-line p-3 text-sm">
	<legend class="px-1 text-xs text-muted">{m.consent_optional_heading()}</legend>
	{#each consentItems as entry, i (i)}
		{#if !entry.required}{@render item(entry, i)}{/if}
	{/each}
	<p class="text-xs text-muted">{m.consent_research_note()}</p>
</fieldset>

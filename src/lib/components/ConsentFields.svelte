<script lang="ts" module>
	import { m } from '$lib/paraglide/messages.js';

	export const consentItems = [
		m.consent_terms,
		m.consent_privacy,
		m.consent_research,
		m.consent_non_diagnostic
	];
</script>

<script lang="ts">
	let { checked = $bindable() }: { checked: boolean[] } = $props();
</script>

<fieldset class="space-y-2 text-sm">
	{#each consentItems as label, i (i)}
		<label class="flex items-start gap-2">
			<input
				type="checkbox"
				class="mt-0.5 rounded border-slate-600 bg-slate-900 text-cyan-400"
				required
				bind:checked={checked[i]}
			/>
			<span>{label()}</span>
		</label>
	{/each}
</fieldset>

<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import { likertLabels } from '$lib/i18n';

	let {
		text,
		disabled = false,
		onanswer,
	}: { text: string; disabled?: boolean; onanswer: (value: number) => void } = $props();
</script>

<fieldset {disabled}>
	<legend class="text-lg leading-relaxed">{text}</legend>
	<p class="mt-1 text-sm text-slate-400">{m.survey_instruction()}</p>
	<div class="mt-6 grid gap-2 sm:grid-cols-5">
		{#each likertLabels as label, i (i)}
			<button
				type="button"
				class="rounded-md border border-slate-700 px-3 py-3 text-sm transition hover:border-cyan-300 hover:text-cyan-300 focus-visible:outline-2 focus-visible:outline-cyan-300"
				onclick={() => onanswer(i + 1)}
			>
				<span class="block font-mono text-xs text-slate-500">{i + 1}</span>
				{label()}
			</button>
		{/each}
	</div>
</fieldset>

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
	<legend class="max-w-3xl text-2xl leading-loose font-medium sm:text-3xl">{text}</legend>
	<p class="mt-1 text-sm text-muted">{m.survey_instruction()}</p>
	<div class="mt-8 grid gap-3 sm:grid-cols-5">
		{#each likertLabels as label, i (i)}
			<button type="button" class="likert-option" onclick={() => onanswer(i + 1)}>
				<span class="option-number">{i + 1}</span>
				{label()}
			</button>
		{/each}
	</div>
</fieldset>

<style>
	.likert-option {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: flex-start;
		gap: 15px;
		min-height: 150px;
		padding: 22px 14px;
		border: 1px solid var(--color-line);
		border-radius: 12px;
		font-size: 13px;
		background: white;
		transition:
			background 180ms ease-out,
			border-color 180ms ease-out;
	}
	.likert-option:hover {
		border-color: var(--color-ocean);
		background: var(--color-mist);
	}
	.option-number {
		display: grid;
		place-items: center;
		width: 30px;
		height: 30px;
		border-radius: 50%;
		background: var(--color-mist);
		font-size: 13px;
		color: var(--color-ocean);
		font-variant-numeric: tabular-nums;
	}
	@media (max-width: 639px) {
		.likert-option {
			min-height: 60px;
			flex-direction: row;
			justify-content: flex-start;
			padding: 12px 18px;
			gap: 18px;
			text-align: left;
		}
	}
</style>

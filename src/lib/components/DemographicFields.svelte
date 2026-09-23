<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	let {
		birthYear = $bindable(),
		birthMonth = $bindable(''),
		gender = $bindable(''),
	}: { birthYear?: number; birthMonth?: string; gender?: string } = $props();
	const id = $props.id();
	const options = [
		{ value: 'male', label: m.signup_gender_male },
		{ value: 'female', label: m.signup_gender_female },
		{ value: 'neither', label: m.signup_gender_neither },
		{ value: 'prefer_not_to_say', label: m.signup_gender_private },
	];
</script>

<div class="space-y-5 border-y border-line py-5">
	<p id={`${id}-note`} class="text-sm leading-relaxed text-body">{m.signup_demographics_note()}</p>
	<fieldset aria-describedby={`${id}-hint ${id}-note`}>
		<legend class="mb-3 text-sm font-medium">{m.signup_birth_heading()}</legend>
		<div class="grid grid-cols-2 gap-3">
			<label class="text-sm">
				{m.signup_birth_year()}
				<input
					class="field"
					type="number"
					inputmode="numeric"
					autocomplete="bday-year"
					min="1"
					max="9999"
					step="1"
					required
					bind:value={birthYear}
				/>
			</label>
			<div class="text-sm">
				<label for={`${id}-month`}>{m.signup_birth_month()}</label>
				<select
					id={`${id}-month`}
					class="field"
					autocomplete="bday-month"
					required
					bind:value={birthMonth}
				>
					<option value="" disabled>{m.signup_select_month()}</option>
					{#each Array.from({ length: 12 }, (_, i) => i + 1) as month (month)}
						<option value={String(month)}>{month}</option>
					{/each}
				</select>
			</div>
		</div>
		<p id={`${id}-hint`} class="mt-2 text-xs text-muted">{m.signup_birth_hint()}</p>
	</fieldset>
	<fieldset aria-describedby={`${id}-note`}>
		<legend class="mb-2 text-sm font-medium">{m.signup_gender_heading()}</legend>
		{#each options as option (option.value)}
			<label class="flex min-h-11 cursor-pointer items-center gap-3 py-2 text-sm">
				<input
					type="radio"
					name={`${id}-gender`}
					value={option.value}
					bind:group={gender}
					required
					class="shrink-0 border-line text-ocean focus:ring-ocean"
				/>
				{option.label()}
			</label>
		{/each}
	</fieldset>
</div>

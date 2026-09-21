<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, type Position } from '$lib/api.svelte';
	import { stageDescription, stageName } from '$lib/i18n';
	import { href } from '$lib/nav';

	const LOW_CONFIDENCE = 0.5;

	let pos = $state<Position | null>(null);
	let error = $state<string | null>(null);

	onMount(() => {
		api
			.position()
			.then((p) => (pos = p))
			.catch((e) => (error = apiErrorMessage(e)));
	});

	const percent = (v: number) => Math.round(v * 100);
</script>

<h1 class="text-2xl font-semibold">{m.profile_title()}</h1>

{#if error}
	<p class="mt-6 alert" role="alert">{error}</p>
{:else if !pos}
	<p role="status" class="mt-6 text-slate-400">{m.common_loading()}</p>
{:else}
	<section class="mt-6 space-y-1">
		<p class="text-3xl font-semibold text-cyan-300">
			{m.profile_observer_no({ no: pos.observer_no })}
		</p>
		<p class="text-sm text-slate-400">{m.profile_participants({ count: pos.participants })}</p>
	</section>

	<section class="mt-8 rounded-lg border border-slate-800 p-5">
		<h2 class="text-sm text-slate-400">{m.profile_stage()}</h2>
		<p class="mt-1 text-lg font-semibold">{stageName[pos.chart.stage]()}</p>
		<p class="mt-2 text-sm text-slate-300">{stageDescription[pos.chart.stage]()}</p>
	</section>

	{#if pos.position && pos.confidence !== undefined}
		<section class="mt-6 space-y-2 rounded-lg border border-slate-800 p-5">
			<h2 class="text-sm text-slate-400">{m.profile_position()}</h2>
			<p class="font-mono">
				{m.profile_position_value({ x: pos.position[0].toFixed(2), y: pos.position[1].toFixed(2) })}
			</p>
			<p class="text-sm">{m.profile_confidence_value({ percent: percent(pos.confidence) })}</p>
			{#if pos.confidence < LOW_CONFIDENCE}
				<p class="text-sm text-amber-300">{m.profile_low_confidence()}</p>
			{/if}
			{#if pos.regions}
				<h3 class="pt-2 text-sm text-slate-400">{m.profile_regions()}</h3>
				<p class="text-sm text-slate-300">{m.profile_region_likely()}</p>
				<ul class="text-sm">
					{#each pos.regions as r (r.lineage_id)}
						<li>{m.profile_region_item({ region: r.lineage_id, percent: percent(r.p) })}</li>
					{/each}
				</ul>
				{#if pos.near_boundary}
					<p class="text-sm text-amber-300">{m.profile_near_boundary()}</p>
				{/if}
			{/if}
		</section>
	{/if}

	<div class="mt-8">
		{#if pos.survey.initial_completed}
			<p class="text-sm text-slate-400">{m.profile_initial_done()}</p>
		{:else}
			<a href={href('/survey/initial')} class="btn-primary">
				{pos.survey.open_session ? m.profile_resume_initial() : m.profile_start_initial()}
			</a>
		{/if}
	</div>
{/if}

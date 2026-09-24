<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, ApiError, type Position, type ChartMap } from '$lib/api.svelte';
	import { stageDescription, stageName, positionText } from '$lib/i18n';
	import { href } from '$lib/nav';
	import UpdateStatus from '$lib/components/UpdateStatus.svelte';
	import SurveyAction from '$lib/components/SurveyAction.svelte';
	import ChartMapView from '$lib/components/ChartMap.svelte';

	const LOW_CONFIDENCE = 0.5;

	let pos = $state<Position | null>(null);
	let map = $state<ChartMap | null>(null);
	let error = $state<string | null>(null);

	onMount(() => {
		api
			.position()
			.then(async (p) => {
				pos = p;
				if (p.position?.length === 3) {
					try {
						const chart = await api.chart();
						if (chart.chart.version === p.chart.version) map = chart.map;
					} catch (e) {
						if (!(e instanceof ApiError && e.status === 404)) throw e;
					}
				}
			})
			.catch((e) => (error = apiErrorMessage(e)));
	});

	const percent = (v: number) => Math.round(v * 100);
</script>

<h1 class="text-2xl font-medium">{m.profile_title()}</h1>
<p class="mt-2 text-sm text-muted">{m.profile_lead()}</p>

{#if error}
	<p class="mt-6 alert" role="alert">{error}</p>
{:else if !pos}
	<p role="status" class="mt-6 text-muted">{m.common_loading()}</p>
{:else}
	<div class="observation-record">
		<section class="observer-identity">
			<h2>{m.profile_observer_no({ no: pos.observer_no })}</h2>
			<p>{m.profile_participants({ count: pos.participants })}</p>
			<div class="mt-5">
				<UpdateStatus updatedAt={pos.updated_at} nextUpdateAt={pos.next_update_at} />
			</div>
		</section>
		<section class="action-panel space-y-4">
			<h2 class="text-lg font-medium">{m.profile_survey_heading()}</h2>
			<p class="text-sm leading-loose text-body">
				{pos.survey.initial_completed ? m.profile_initial_done() : m.profile_initial_lead()}
			</p>
			<SurveyAction survey={pos.survey} />
		</section>
	</div>
	<section class="stage-record record-panel">
		<div>
			<h2 class="text-sm text-muted">{m.profile_stage()}</h2>
			<p class="mt-2 text-xl font-medium">{stageName(pos.chart.stage)}</p>
		</div>
		<p class="max-w-lg text-sm leading-loose text-body">{stageDescription(pos.chart.stage)}</p>
	</section>
	{#if pos.position && pos.confidence !== undefined}
		<section class="record-panel space-y-3">
			<h2 class="text-sm text-muted">{m.profile_position()}</h2>
			<p class="font-mono text-2xl">
				{positionText(pos.position)}
			</p>
			<p class="text-sm">{m.profile_confidence_value({ percent: percent(pos.confidence) })}</p>
			{#if pos.position.length === 3}
				<ChartMapView
					{map}
					position={pos.position}
					region={pos.credible_region}
					label={m.ocean_title()}
				/>
			{/if}
			{#if pos.confidence < LOW_CONFIDENCE}<p class="text-sm text-warning">
					{m.profile_low_confidence()}
				</p>{/if}
			{#if pos.inference_mode}<p class="text-xs text-muted">
					{pos.inference_mode === 'joint' ? m.profile_inference_joint() : m.profile_inference_cut()}
				</p>{/if}
			{#if pos.credible_region}
				<a href={href('/chart')} class="inline-block text-sm text-ocean underline"
					>{m.profile_see_isobath()}</a
				>
			{/if}
			{#if pos.regions}
				<h3 class="pt-5 text-sm text-muted">{m.profile_regions()}</h3>
				<p class="text-sm text-body">{m.profile_region_likely()}</p>
				<ul class="region-list">
					{#each pos.regions as r (r.lineage_id)}
						<li>
							<span>{m.profile_region_item({ region: r.lineage_id, percent: percent(r.p) })}</span
							><meter min="0" max="1" value={r.p} aria-label={r.lineage_id}></meter>
						</li>
					{/each}
				</ul>
				{#if pos.near_boundary}<p class="text-sm text-warning">{m.profile_near_boundary()}</p>{/if}
				{#if pos.unmatched}<p class="text-sm text-muted">
						{m.profile_unmatched({ percent: percent(pos.unmatched.total) })}
					</p>{/if}
			{:else}
				<p class="pt-5 text-sm text-body">{m.profile_regions_none()}</p>
			{/if}
		</section>
	{/if}
	{#if !pos.position}<p class="record-panel text-sm leading-loose text-body">
			{m.profile_position_empty()}
		</p>{/if}
	<div class="mt-5 flex flex-wrap items-center gap-3">
		<a href={href('/chart')} class="btn-secondary">{m.profile_links_chart()}</a>
		<a href={href('/journey')} class="btn-secondary">{m.profile_links_journey()}</a>
	</div>
{/if}

<style>
	.observation-record {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 40px;
		align-items: center;
		margin: 36px 0;
	}
	.observer-identity h2 {
		font-size: clamp(1.6rem, 3vw, 2.2rem);
		color: var(--color-ocean);
		font-weight: 500;
	}
	.observer-identity > p {
		margin-top: 12px;
		color: var(--color-muted);
		font-size: 13px;
	}
	.stage-record {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 36px;
	}
	.region-list {
		max-width: 540px;
	}
	.region-list li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 24px;
		padding: 12px 0;
		border-bottom: 1px solid var(--color-line);
		font-size: 13px;
	}
	meter {
		width: 100px;
		height: 6px;
		background: var(--color-mist);
		border: 0;
	}
	meter::-webkit-meter-bar {
		background: var(--color-mist);
		border: 0;
	}
	meter::-webkit-meter-optimum-value {
		background: var(--color-ocean);
	}
	meter::-moz-meter-bar {
		background: var(--color-ocean);
	}
	@media (max-width: 640px) {
		.observation-record {
			grid-template-columns: 1fr;
			gap: 28px;
		}
		.stage-record {
			flex-direction: column;
			align-items: start;
			gap: 14px;
		}
	}
</style>

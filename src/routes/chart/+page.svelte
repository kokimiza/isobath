<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import {
		api,
		apiErrorMessage,
		ApiError,
		type ChartResponse,
		type Meta,
		type Position,
	} from '$lib/api.svelte';
	import { auth } from '$lib/auth.svelte';
	import { stageDescription, stageName } from '$lib/i18n';
	import { href } from '$lib/nav';
	import ChartMapView from '$lib/components/ChartMap.svelte';
	import SurveyAction from '$lib/components/SurveyAction.svelte';
	import UpdateStatus from '$lib/components/UpdateStatus.svelte';
	import Scan from '@lucide/svelte/icons/scan';

	// Public and prerendered: the chart itself needs no login; the own position is added if logged in.
	let chart = $state<ChartResponse | null>(null);
	let meta = $state<Meta | null>(null);
	let mine = $state<Position | null>(null);
	let error = $state<string | null>(null);
	let loaded = $state(false);

	onMount(async () => {
		try {
			meta = await api.meta();
			chart = await api.chart().catch((e) => {
				if (e instanceof ApiError && e.status === 404) return null; // no published estimate yet
				throw e;
			});
		} catch (e) {
			error = apiErrorMessage(e);
		}
		loaded = true;
	});

	$effect(() => {
		mine = null;
		if (!auth.session) return;
		let active = true;
		api
			.position()
			.then((p) => {
				if (active) mine = p;
			})
			.catch(() => undefined); // the public chart and survey entry still work
		return () => {
			active = false;
		};
	});

	// positions of another chart version live in another coordinate system (FR-JNY-03)
	const own = $derived(
		mine?.position && (!chart || mine.chart.version === chart.chart.version) ? mine : null,
	);
</script>

<h1 class="text-2xl font-semibold">{m.chart_title()}</h1>
<p class="mt-2 text-sm text-muted">{m.chart_lead()}</p>

{#if error}
	<p class="mt-6 alert" role="alert">{error}</p>
{:else if !loaded}
	<p role="status" class="mt-6 text-muted">{m.common_loading()}</p>
{:else if meta}
	<section class="chart-summary">
		<div>
			<p class="text-lg font-medium">{stageName(meta.chart.stage)}</p>
			<p class="mt-2 max-w-lg text-sm text-body">{stageDescription(meta.chart.stage)}</p>
		</div>
		<dl>
			<div>
				<dt>{m.chart_participants()}</dt>
				<dd>{meta.participants.toLocaleString()}</dd>
			</div>
			<div>
				<dt>{m.chart_version()}</dt>
				<dd>{meta.chart.version ?? '—'}</dd>
			</div>
		</dl>
	</section>

	{#if chart ?? own}
		<div class="chart-canvas">
			<ChartMapView
				map={chart?.map}
				position={own?.position}
				region={own?.credible_region}
				label={m.chart_map_label({ participants: meta.participants })}
			/>
		</div>
		<ul class="mt-4 space-y-1 text-xs text-muted">
			{#if chart}<li>{m.chart_legend_density()}</li>{/if}
			{#if own}<li>{m.chart_legend_you()}</li>{/if}
			{#if own?.credible_region}<li>{m.chart_legend_isobath()}</li>{/if}
			{#if chart}<li>{m.chart_legend_suppressed({ k: chart.map.k })}</li>{/if}
		</ul>
	{:else}
		<section class="uncharted">
			<Scan size={42} strokeWidth={1} aria-hidden="true" />
			<h2>{m.chart_empty_title()}</h2>
			<p>{m.chart_empty_body()}</p>
			<p class="text-xs">{m.chart_not_ready()}</p>
		</section>
	{/if}
	<div class="mt-5">
		<UpdateStatus updatedAt={meta.updated_at} nextUpdateAt={meta.next_update_at} />
	</div>
{/if}

<section class="chart-invitation">
	<div>
		<h2 class="text-lg font-semibold">{m.chart_join_title()}</h2>
		<p class="text-sm leading-relaxed text-body">{m.chart_join_lead()}</p>
	</div>
	<div class="flex flex-wrap items-center gap-3">
		<SurveyAction survey={mine?.survey} />
		{#if auth.session}
			<a href={href('/profile')} class="btn-secondary">{m.nav_my_page()}</a>
		{/if}
	</div>
</section>

<style>
	.chart-summary {
		margin-top: 36px;
		border-top: 1px solid var(--color-line);
		padding-top: 24px;
		display: flex;
		justify-content: space-between;
		align-items: start;
		gap: 30px;
	}
	dl {
		display: flex;
		gap: 30px;
		flex-shrink: 0;
	}
	dt {
		font-size: 11px;
		color: var(--color-muted);
	}
	dd {
		font-size: 18px;
		margin-top: 6px;
		font-variant-numeric: tabular-nums;
	}
	.chart-canvas {
		margin-top: 28px;
		background: var(--color-mist);
		border-radius: 16px;
		padding: 26px;
		display: flex;
		justify-content: center;
	}
	.uncharted {
		min-height: 320px;
		background: var(--color-mist);
		border-radius: 16px;
		margin-top: 28px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 18px;
		padding: 40px;
		text-align: center;
		color: var(--color-ocean);
	}
	.uncharted h2 {
		font-size: 24px;
		color: var(--color-ink);
	}
	.uncharted p {
		max-width: 36em;
		font-size: 13px;
		line-height: 2;
		color: var(--color-body);
	}
	.chart-invitation {
		margin-top: 40px;
		padding-top: 32px;
		border-top: 1px solid var(--color-line);
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 30px;
	}
	.chart-invitation p {
		margin-top: 10px;
		max-width: 34em;
	}
	@media (max-width: 640px) {
		.chart-summary,
		.chart-invitation {
			flex-direction: column;
		}
		.uncharted {
			padding: 28px 20px;
		}
		.uncharted h2 {
			font-size: 20px;
		}
		.chart-canvas {
			padding: 8px;
		}
	}
</style>

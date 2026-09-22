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
	import ChartMapView from '$lib/components/ChartMap.svelte';
	import UpdateStatus from '$lib/components/UpdateStatus.svelte';

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
				if (e instanceof ApiError && e.status === 404) return null; // no chart before PROTO
				throw e;
			});
		} catch (e) {
			error = apiErrorMessage(e);
		}
		loaded = true;
	});

	$effect(() => {
		if (!auth.session || !chart) return;
		api
			.position()
			.then((p) => (mine = p.chart.version === chart?.chart.version ? p : null))
			.catch(() => (mine = null)); // the public chart works without the personal overlay
	});
</script>

<h1 class="text-2xl font-semibold">{m.chart_title()}</h1>

{#if error}
	<p class="mt-6 alert" role="alert">{error}</p>
{:else if !loaded}
	<p role="status" class="mt-6 text-slate-400">{m.common_loading()}</p>
{:else if meta}
	<section class="mt-6 space-y-2">
		<p class="text-lg font-semibold">{stageName[meta.chart.stage]()}</p>
		<p class="text-sm text-slate-300">{stageDescription[meta.chart.stage]()}</p>
		<UpdateStatus updatedAt={meta.updated_at} nextUpdateAt={meta.next_update_at} />
	</section>

	{#if chart}
		<div class="mt-6">
			<ChartMapView
				map={chart.map}
				position={mine?.position ?? null}
				label={m.chart_map_label({ participants: meta.participants })}
			/>
		</div>
		<ul class="mt-4 space-y-1 text-xs text-slate-400">
			<li>{m.chart_legend_density()}</li>
			{#if mine?.position}<li>{m.chart_legend_you()}</li>{/if}
			<li>{m.chart_legend_suppressed({ k: chart.map.k })}</li>
		</ul>
	{:else}
		<p class="mt-6 rounded-lg border border-slate-800 p-5 text-sm text-slate-300">
			{m.chart_not_ready()}
		</p>
	{/if}
{/if}

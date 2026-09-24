<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { api, ApiError, type Snapshot } from '$lib/api.svelte';
	import { formatUpdateTime, positionText } from '$lib/i18n';
	import { href } from '$lib/nav';
	import ChartMapView from '$lib/components/ChartMap.svelte';

	import { resource } from '$lib/resource.svelte';
	import LoadStatus from '$lib/components/LoadStatus.svelte';
	let snapshots = $state<Snapshot[] | null>(null);
	let cursor: number | undefined;
	let hasMore = $state(false);
	const historyRead = resource((signal) => api.history(cursor, signal));
	const chartRead = resource(async (signal) => {
		try {
			return await api.chart(signal);
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) return null;
			throw e;
		}
	});
	const map = $derived(
		chartRead.data?.chart.version === snapshots?.[0]?.chart.version ? chartRead.data?.map : null,
	);
	async function loadMore() {
		if (historyRead.pending) return;
		const page = await historyRead.load();
		if (!page) return;
		const first = snapshots === null;
		snapshots = [
			...(snapshots ?? []),
			...page.items.filter((item) => !snapshots?.some((s) => s.id === item.id)),
		];
		cursor = page.next_cursor ?? undefined;
		hasMore = cursor !== undefined;
		if (first && snapshots.length) void chartRead.load();
	}
	onMount(() => {
		void loadMore();
	});

	// Positions from different chart versions live in different coordinate systems (FR-JNY-03):
	// the trail only connects snapshots of the current version.
	const current = $derived(snapshots?.[0]?.chart.version);
	const trail = $derived(
		(snapshots ?? [])
			.filter((s) => s.chart.version === current)
			.map((s) => s.position)
			.reverse(),
	);
	const olderVersions = $derived((snapshots ?? []).some((s) => s.chart.version !== current));
	const percent = (v: number) => Math.round(v * 100);
</script>

<h1 class="text-2xl font-semibold">{m.journey_title()}</h1>
<p class="mt-2 text-sm text-muted">{m.journey_lead()}</p>

<LoadStatus pending={historyRead.pending} error={historyRead.error} onretry={loadMore} />
{#if snapshots?.length === 0}
	<p class="mt-6 rounded-lg border border-line p-5 text-sm text-body">
		{m.journey_empty()}
	</p>
	<a href={href('/profile')} class="mt-4 btn-primary">{m.nav_overview()}</a>
{:else if snapshots}
	<LoadStatus
		pending={chartRead.pending}
		error={chartRead.error}
		onretry={() => chartRead.load()}
	/>
	<div class="mt-6">
		<ChartMapView
			{map}
			{trail}
			position={snapshots[0].position}
			region={snapshots[0].credible_region}
			label={m.journey_map_label({ count: trail.length })}
		/>
	</div>
	{#if snapshots[0].credible_region && snapshots[0].position.length === 2}
		<p class="mt-3 text-xs text-muted">{m.chart_legend_isobath()}</p>
	{/if}
	{#if olderVersions}
		<p class="mt-3 text-xs text-muted">{m.journey_version_note({ version: current ?? '' })}</p>
	{/if}

	<ol class="mt-8 divide-y divide-line text-sm">
		{#each snapshots as s, i (s.id)}
			{#if i > 0 && s.chart.version !== snapshots[i - 1].chart.version}
				<li class="py-2 text-xs text-warning">
					{m.journey_version_boundary({ version: snapshots[i - 1].chart.version })}
				</li>
			{/if}
			<li class="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 py-3">
				<span class="text-body">{formatUpdateTime(s.at)}</span>
				<span class="font-mono text-muted">
					{positionText(s.position)}
				</span>
				<span class="text-muted">
					{m.profile_confidence_value({ percent: percent(s.confidence) })}
				</span>
			</li>
		{/each}
	</ol>
	{#if hasMore && !historyRead.error}<button
			type="button"
			class="mt-4 btn-secondary"
			disabled={historyRead.pending}
			onclick={loadMore}>{m.journey_load_more()}</button
		>{/if}
{/if}

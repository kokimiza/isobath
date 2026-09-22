<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { api, apiErrorMessage, ApiError, type ChartMap, type Snapshot } from '$lib/api.svelte';
	import { formatUpdateTime } from '$lib/i18n';
	import { href } from '$lib/nav';
	import ChartMapView from '$lib/components/ChartMap.svelte';

	const MAX_PAGES = 10; // 500 nightly updates is well over a year

	let snapshots = $state<Snapshot[] | null>(null);
	let map = $state<ChartMap | null>(null);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const all: Snapshot[] = [];
			let cursor: number | undefined;
			for (let i = 0; i < MAX_PAGES; i++) {
				const page = await api.history(cursor);
				all.push(...page.items);
				if (!page.next_cursor) break;
				cursor = page.next_cursor;
			}
			snapshots = all; // newest first
			if (all.length === 0) return;
			map = await api
				.chart()
				.then((c) => (c.chart.version === all[0]?.chart.version ? c.map : null))
				.catch((e: unknown) => {
					if (e instanceof ApiError && e.status === 404) return null; // no chart before PROTO
					throw e;
				});
		} catch (e) {
			error = apiErrorMessage(e);
		}
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

{#if error}
	<p class="mt-6 alert" role="alert">{error}</p>
{:else if !snapshots}
	<p role="status" class="mt-6 text-muted">{m.common_loading()}</p>
{:else if snapshots.length === 0}
	<p class="mt-6 rounded-lg border border-line p-5 text-sm text-body">
		{m.journey_empty()}
	</p>
	<a href={href('/profile')} class="mt-4 btn-primary">{m.nav_overview()}</a>
{:else}
	<div class="mt-6">
		<ChartMapView
			{map}
			{trail}
			position={snapshots[0].position}
			label={m.journey_map_label({ count: trail.length })}
		/>
	</div>
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
					{m.profile_position_value({ x: s.position[0].toFixed(2), y: s.position[1].toFixed(2) })}
				</span>
				<span class="text-muted">
					{m.profile_confidence_value({ percent: percent(s.confidence) })}
				</span>
			</li>
		{/each}
	</ol>
{/if}

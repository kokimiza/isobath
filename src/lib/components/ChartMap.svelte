<script lang="ts">
	import type { ChartMap, CredibleRegion } from '$lib/api.svelte';
	import ChartMap2D from './ChartMap2D.svelte';
	import OceanChart3D from './OceanChart3D.svelte';
	let {
		map = null,
		position = null,
		region = null,
		trail = [],
		label,
	}: {
		map?: ChartMap | null;
		position?: number[] | null;
		region?: CredibleRegion | null;
		trail?: number[][];
		label: string;
	} = $props();
	const spatial = $derived(position ? position.length === 3 : map?.dimension === 3);
</script>

{#if spatial}
	<OceanChart3D {map} {position} {region} {trail} {label} />
{:else}
	<ChartMap2D {map} {position} {region} {trail} {label} />
{/if}

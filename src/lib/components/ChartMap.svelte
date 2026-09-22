<script lang="ts">
	import type { ChartMap } from '$lib/api.svelte';

	/**
	 * Aggregated density grid from the nightly batch, with optional own position / journey.
	 * Single hue, opacity = density: no colour scale that reads as better/worse (FR-UI-01).
	 */
	let {
		map = null,
		position = null,
		trail = [],
		label,
	}: {
		map?: ChartMap | null;
		position?: number[] | null;
		trail?: number[][];
		label: string;
	} = $props();

	const SIZE = 100;
	const extent = $derived(map?.extent ?? [-3, 3, -3, 3]);
	const bins = $derived(map?.bins ?? 24);
	const cell = $derived(SIZE / bins);
	const max = $derived(Math.max(1, ...(map?.counts.flat() ?? [0])));

	// map coordinates -> SVG (y grows upward on the chart)
	function sx(x: number) {
		const [x0, x1] = extent;
		return ((Math.min(Math.max(x, x0), x1) - x0) / (x1 - x0)) * SIZE;
	}
	function sy(y: number) {
		const [, , y0, y1] = extent;
		return SIZE - ((Math.min(Math.max(y, y0), y1) - y0) / (y1 - y0)) * SIZE;
	}

	const cells = $derived(
		(map?.counts ?? []).flatMap((column, i) =>
			column.flatMap((count, j) =>
				count > 0 ? [{ x: i * cell, y: SIZE - (j + 1) * cell, opacity: count / max }] : [],
			),
		),
	);
	const path = $derived(trail.map(([x, y]) => `${sx(x)},${sy(y)}`).join(' '));
</script>

<svg
	viewBox="0 0 {SIZE} {SIZE}"
	role="img"
	aria-label={label}
	class="aspect-square w-full max-w-md rounded-lg border border-slate-800 bg-slate-900"
>
	<!-- sea grid -->
	{#each [25, 50, 75] as g (g)}
		<line x1={g} y1="0" x2={g} y2={SIZE} class="stroke-slate-800" stroke-width="0.2" />
		<line x1="0" y1={g} x2={SIZE} y2={g} class="stroke-slate-800" stroke-width="0.2" />
	{/each}

	{#each cells as c (`${c.x}-${c.y}`)}
		<rect
			x={c.x}
			y={c.y}
			width={cell}
			height={cell}
			class="fill-cyan-400"
			fill-opacity={0.15 + 0.7 * c.opacity}
		/>
	{/each}

	{#if trail.length > 1}
		<polyline
			points={path}
			fill="none"
			class="stroke-amber-300"
			stroke-width="0.6"
			stroke-linejoin="round"
		/>
		{#each trail.slice(0, -1) as [x, y], i (i)}
			<circle cx={sx(x)} cy={sy(y)} r="0.9" class="fill-amber-300/60" />
		{/each}
	{/if}

	{#if position}
		<circle
			cx={sx(position[0])}
			cy={sy(position[1])}
			r="2.2"
			class="fill-amber-300 stroke-slate-950"
			stroke-width="0.6"
		/>
	{/if}
</svg>

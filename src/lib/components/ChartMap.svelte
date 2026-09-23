<script lang="ts">
	import { contours } from 'd3-contour';
	import type { ChartMap, CredibleRegion } from '$lib/api.svelte';

	/**
	 * Aggregated density grid from the nightly batch, with optional own position / journey.
	 * Single hue, opacity = density: no colour scale that reads as better/worse (FR-UI-01).
	 * The own posterior is drawn as isobaths: highest-density regions holding 95/80/50% of it.
	 */
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

	const ISOBATH_LEVELS = [0.95, 0.8, 0.5];
	const GRID = [25, 50, 75];
	// Stable across hydration and unique when several charts share a page.
	const id = $props.id();
	const clipId = `${id}-water`;

	const SIZE = 100;
	const extent = $derived(map?.extent ?? [-3, 3, -3, 3]);
	const bins = $derived(map?.bins ?? 24);
	const cell = $derived(SIZE / bins);
	const max = $derived(Math.max(1, ...(map?.counts.flat() ?? [0])));

	// map coordinates -> SVG (y grows upward on the chart); points are clamped, shapes are clipped
	const tx = (x: number) => ((x - extent[0]) / (extent[1] - extent[0])) * SIZE;
	const ty = (y: number) => SIZE - ((y - extent[2]) / (extent[3] - extent[2])) * SIZE;
	const sx = (x: number) => tx(Math.min(Math.max(x, extent[0]), extent[1]));
	const sy = (y: number) => ty(Math.min(Math.max(y, extent[2]), extent[3]));

	const isobaths = $derived.by(() => {
		if (region?.kind !== 'grid_hpd') return [];
		const { bins, cell_probability: p } = region;
		const [ex, ey] = region.edges;
		// d3-contour wants x varying fastest; the API stores ix * bins + iy
		const values = new Array<number>(bins * bins);
		for (let ix = 0; ix < bins; ix++)
			for (let iy = 0; iy < bins; iy++) values[iy * bins + ix] = p[ix * bins + iy];
		const sorted = [...p].sort((a, b) => b - a);
		const grid = contours().size([bins, bins]);
		// grid coordinate g spans cell edges: g = 0 is edges[0], g = bins is edges[bins]
		const gx = (g: number) => tx(ex[0] + (g / bins) * (ex[bins] - ex[0]));
		const gy = (g: number) => ty(ey[0] + (g / bins) * (ey[bins] - ey[0]));
		return ISOBATH_LEVELS.map((level) => {
			// same rule as the batch: add cells by density until the mass reaches the level
			let sum = 0;
			const threshold = sorted.find((v) => (sum += v) >= level) ?? sorted[sorted.length - 1];
			const d = grid
				.contour(values, threshold)
				.coordinates.flat()
				.map((ring) => `M${ring.map(([x, y]) => `${gx(x)},${gy(y)}`).join('L')}Z`)
				.join('');
			return { level, d };
		});
	});

	const cells = $derived(
		(map?.counts ?? []).flatMap((column, i) =>
			column.flatMap((count, j) =>
				count > 0 ? [{ x: i * cell, y: SIZE - (j + 1) * cell, opacity: count / max }] : [],
			),
		),
	);
	const path = $derived(trail.map(([x, y]) => `${sx(x)},${sy(y)}`).join(' '));
</script>

<svg viewBox="-4 -4 108 108" role="img" aria-label={label} class="chart-map">
	<defs>
		<clipPath id={clipId}>
			<rect width={SIZE} height={SIZE} rx="1.5" />
		</clipPath>
	</defs>
	<rect class="water" width={SIZE} height={SIZE} rx="1.5" />
	<g clip-path={`url(#${clipId})`}>
		<!-- Aggregate observations remain discrete: do not invent density between cells. -->
		<g class="density">
			{#each cells as c (`${c.x}-${c.y}`)}
				<rect x={c.x} y={c.y} width={cell} height={cell} fill-opacity={0.15 + 0.7 * c.opacity} />
			{/each}
		</g>

		<!-- A quiet reference grid stays visible over the density field. -->
		<g class="grid">
			{#each GRID as g (g)}
				<line x1={g} y1="0" x2={g} y2={SIZE} />
				<line x1="0" y1={g} x2={SIZE} y2={g} />
			{/each}
		</g>

		<!-- own posterior: nested fills darken toward the most probable area -->
		<g class="posterior">
			{#each isobaths as iso (iso.level)}
				<defs>
					<path id={`${id}-isobath-${iso.level}`} d={iso.d} fill-rule="evenodd" />
				</defs>
				<use href={`#${id}-isobath-${iso.level}`} class="isobath-casing" />
				<use
					href={`#${id}-isobath-${iso.level}`}
					class="isobath"
					class:outer={iso.level === 0.95}
					stroke-dasharray={iso.level === 0.95 ? undefined : iso.level === 0.8 ? '5 4' : '1 4'}
				/>
			{/each}
			{#if region?.kind === 'segment'}
				{@const [[x1, y1], [x2, y2]] = region.endpoints}
				<line x1={tx(x1)} y1={ty(y1)} x2={tx(x2)} y2={ty(y2)} class="credible-segment" />
			{/if}
		</g>

		{#if trail.length > 1}
			<g class="journey">
				<polyline points={path} class="trail-casing" />
				<polyline points={path} class="trail" />
				{#each trail.slice(0, -1) as [x, y], i (i)}
					<circle cx={sx(x)} cy={sy(y)} r="0.65" class="past-position" />
				{/each}
			</g>
		{/if}

		{#if position}
			<circle cx={sx(position[0])} cy={sy(position[1])} r="1.5" class="current-position" />
		{/if}
	</g>

	<!-- The rim and registration ticks belong to the frame, not to the data. -->
	<g class="frame" aria-hidden="true">
		<rect width={SIZE} height={SIZE} rx="1.5" />
		{#each GRID as g (g)}
			<line x1={g} y1="-1.5" x2={g} y2="0" />
			<line x1={g} y1={SIZE} x2={g} y2={SIZE + 1.5} />
			<line x1="-1.5" y1={g} x2="0" y2={g} />
			<line x1={SIZE} y1={g} x2={SIZE + 1.5} y2={g} />
		{/each}
	</g>
</svg>

<style>
	.chart-map {
		--water: #e6eff0;
		--grid: #9fbfc8;
		--journey: #8c4d20;
		display: block;
		width: 100%;
		max-width: 36rem;
		aspect-ratio: 1;
		border: 1px solid var(--color-line);
		border-radius: 12px;
		background: var(--color-paper);
	}

	/* Keep line weights legible on a phone without making desktop lines heavy. */
	line,
	path,
	use,
	polyline,
	circle,
	.frame rect {
		vector-effect: non-scaling-stroke;
	}

	.water {
		fill: var(--water);
	}
	.density {
		fill: var(--color-ocean);
	}
	.grid {
		stroke: var(--grid);
		stroke-width: 0.6;
		stroke-opacity: 0.55;
	}
	.frame {
		fill: none;
		stroke: var(--grid);
		stroke-width: 0.8;
	}
	.posterior {
		stroke-linejoin: round;
		stroke-linecap: round;
	}
	.isobath-casing {
		fill: var(--journey);
		fill-opacity: 0.055;
		stroke: var(--color-paper);
		stroke-opacity: 0.8;
		stroke-width: 3.5;
	}
	.isobath {
		fill: none;
		stroke: var(--journey);
		stroke-opacity: 1;
		stroke-width: 1.2;
	}
	.isobath.outer {
		stroke-width: 1.6;
	}
	.credible-segment {
		stroke: var(--journey);
		stroke-opacity: 0.4;
		stroke-width: 6;
	}
	.journey {
		fill: none;
		stroke-linejoin: round;
		stroke-linecap: round;
	}
	.trail-casing {
		stroke: var(--color-paper);
		stroke-width: 4.5;
	}
	.trail {
		stroke: var(--journey);
		stroke-width: 1.8;
	}
	.past-position {
		fill: var(--color-paper);
		stroke: var(--journey);
		stroke-width: 1.5;
	}
	.current-position {
		fill: var(--journey);
		stroke: var(--color-paper);
		stroke-width: 3;
	}
</style>

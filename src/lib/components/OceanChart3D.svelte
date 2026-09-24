<script lang="ts">
	import { onMount } from 'svelte';
	import { drag } from 'd3-drag';
	import { select } from 'd3-selection';
	import { scaleLinear } from 'd3-scale';
	import { zoom, zoomIdentity, type ZoomBehavior } from 'd3-zoom';
	import {
		ArrowLeft,
		ArrowRight,
		ArrowUp,
		ArrowDown,
		Plus,
		Minus,
		RotateCcw,
	} from '@lucide/svelte';
	import type { ChartMap, CredibleRegion } from '$lib/api.svelte';
	import { m } from '$lib/paraglide/messages.js';
	import {
		isosurface,
		hpdThreshold,
		rotate,
		signed,
		type Triangle,
		type Vec3,
	} from '$lib/chart3d/geometry';

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
	let canvas: HTMLCanvasElement;
	let width = $state(720),
		height = $state(450);
	let yaw = $state(-0.6),
		pitch = $state(0.48),
		magnification = $state(1);
	let showUncertainty = $state(true),
		showSeas = $state(true);
	let ready = $state(false),
		unavailable = $state(false);
	let zoomer: ZoomBehavior<HTMLCanvasElement, unknown>;
	const palette = ['#627f70', '#82799e', '#9b8056', '#51857e', '#996d84'];
	const axes = ['X', 'Y', 'Z'];
	const own = $derived(region?.kind === 'volume_hpd' ? region : null);
	const meanSea = $derived(own?.sea_at_mean);
	const surfaces = $derived.by(() => {
		const result: { triangles: Triangle[]; color: string; personal: boolean; inner: boolean }[] =
			[];
		if (own) {
			const centers = own.edges.map((edge) =>
				edge.slice(0, -1).map((v, i) => (v + edge[i + 1]) / 2),
			);
			for (const mass of [0.95, 0.5])
				result.push({
					triangles: isosurface(
						centers,
						own.cell_probability,
						hpdThreshold(own.cell_probability, mass),
					),
					color: '#247d92',
					personal: true,
					inner: mass === 0.5,
				});
		}
		if (map?.seas) {
			const sea = map.seas;
			const coordinates = sea.bounds.map(([lo, hi]) =>
				Array.from({ length: sea.bins }, (_, i) => lo + (i * (hi - lo)) / (sea.bins - 1)),
			);
			sea.regions.forEach((r, i) =>
				result.push({
					triangles: isosurface(coordinates, r.values, sea.threshold),
					color: palette[i % palette.length],
					personal: false,
					inner: false,
				}),
			);
		}
		return result;
	});
	// Fit actual posterior surfaces as well as the published [-3,3] sea window.
	const radius = $derived.by(() => {
		let extent = 3;
		for (const surface of surfaces)
			for (const triangle of surface.triangles)
				for (const point of triangle)
					for (const value of point) extent = Math.max(extent, Math.abs(value));
		for (const point of [position, ...trail])
			if (point?.length === 3)
				for (const value of point) extent = Math.max(extent, Math.abs(value));
		return extent * 1.12;
	});

	function turn(dx: number, dy: number) {
		yaw += dx;
		pitch = Math.max(-1.35, Math.min(1.35, pitch + dy));
	}
	function enlarge(factor: number) {
		if (zoomer) zoomer.scaleBy(select(canvas), factor);
	}
	function reset() {
		yaw = -0.6;
		pitch = 0.48;
		if (zoomer) zoomer.transform(select(canvas), zoomIdentity);
	}

	onMount(() => {
		const selection = select(canvas);
		selection.call(
			drag<HTMLCanvasElement, unknown>()
				.container(canvas)
				.filter((event) => !event.button && (!event.touches || event.touches.length === 1))
				.on('drag', (event) => turn(event.dx * 0.008, event.dy * 0.008)),
		);
		zoomer = zoom<HTMLCanvasElement, unknown>()
			.scaleExtent([0.6, 3])
			.filter((event) => event.type === 'wheel' || event.touches?.length === 2)
			.on('zoom', (event) => {
				magnification = event.transform.k;
			});
		selection.call(zoomer).on('dblclick.zoom', null);
		const observer = new ResizeObserver(([entry]) => {
			width = entry.contentRect.width;
			height = width < 480 ? 330 : Math.min(500, width * 0.62);
		});
		observer.observe(canvas.parentElement!);
		unavailable = !canvas.getContext('2d');
		ready = true;
		return () => {
			observer.disconnect();
			selection.on('.drag', null).on('.zoom', null);
		};
	});

	$effect(() => {
		if (!ready || unavailable) return;
		const size = { width, height, yaw, pitch, magnification, radius };
		const visible = surfaces.filter((s) => (s.personal ? showUncertainty : showSeas));
		const point = position,
			path = trail,
			volume = map?.volume;
		const you = m.ocean_you();
		const frame = requestAnimationFrame(() => paint(size, visible, point, path, volume, you));
		return () => cancelAnimationFrame(frame);
	});

	function paint(
		size: {
			width: number;
			height: number;
			yaw: number;
			pitch: number;
			magnification: number;
			radius: number;
		},
		visible: typeof surfaces,
		point: number[] | null,
		path: number[][],
		volume: ChartMap['volume'],
		you: string,
	) {
		const ctx = canvas.getContext('2d');
		if (!ctx) return;
		const { width: w, height: h } = size;
		const dpi = Math.min(devicePixelRatio || 1, 2);
		canvas.width = w * dpi;
		canvas.height = h * dpi;
		ctx.scale(dpi, dpi);
		const scale = scaleLinear().domain([-size.radius, size.radius]).range([-1, 1]);
		const unit = Math.min(w * 0.32, h * 0.34) * size.magnification;
		const project = (v: Vec3): Vec3 => {
			const p = rotate(v, size.yaw, size.pitch);
			return [w / 2 + scale(p[0]) * unit, h * 0.5 + scale(p[1]) * unit, p[2]];
		};
		const line = (a: Vec3, b: Vec3, color: string, dash: number[] = []) => {
			const p = project(a),
				q = project(b);
			ctx.beginPath();
			ctx.moveTo(p[0], p[1]);
			ctx.lineTo(q[0], q[1]);
			ctx.strokeStyle = color;
			ctx.lineWidth = 1;
			ctx.setLineDash(dash);
			ctx.stroke();
			ctx.setLineDash([]);
		};
		// A measured floor, not a decorative background grid.
		const floor = -Math.min(3, size.radius);
		for (let tick = -3; tick <= 3; tick++) {
			line([-3, tick, floor], [3, tick, floor], '#cedfe2');
			line([tick, -3, floor], [tick, 3, floor], '#cedfe2');
		}
		for (let d = 0; d < 3; d++) {
			const low: Vec3 = [0, 0, 0],
				high: Vec3 = [0, 0, 0];
			low[d] = -size.radius * 0.92;
			high[d] = size.radius * 0.92;
			line(low, high, '#9bbac2', [3, 5]);
			ctx.font = '12px sans-serif';
			ctx.fillStyle = '#426674';
			ctx.textAlign = 'center';
			for (const sign of [-1, 1]) {
				const end = project(sign < 0 ? low : high);
				ctx.fillText(`${sign < 0 ? '−' : '+'}${axes[d]}`, end[0], end[1] - 8);
			}
		}
		const faces = visible.flatMap((s) =>
			s.triangles.map((triangle) => ({
				points: triangle.map(project),
				...s,
				triangles: undefined,
			})),
		);
		faces.sort(
			(a, b) => b.points.reduce((v, p) => v + p[2], 0) - a.points.reduce((v, p) => v + p[2], 0),
		);
		for (const face of faces) {
			ctx.beginPath();
			face.points.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
			ctx.closePath();
			ctx.fillStyle = face.color;
			ctx.globalAlpha = face.inner ? 0.2 : face.personal ? 0.065 : 0.12;
			ctx.fill();
			ctx.strokeStyle = face.color;
			ctx.globalAlpha = face.personal ? 0.075 : 0.055;
			ctx.lineWidth = 0.45;
			ctx.stroke();
		}
		ctx.globalAlpha = 1;
		if (volume)
			volume.counts.forEach((count, index) => {
				if (!count) return;
				const n = volume.bins,
					indices = [Math.floor(index / n ** 2), Math.floor(index / n) % n, index % n];
				const xyz = indices.map(
					(i, d) =>
						volume.bounds[d][0] + ((i + 0.5) * (volume.bounds[d][1] - volume.bounds[d][0])) / n,
				) as Vec3;
				const p = project(xyz);
				ctx.beginPath();
				ctx.arc(p[0], p[1], Math.min(5, 1.3 + Math.log1p(count) / 2), 0, Math.PI * 2);
				ctx.fillStyle = '#648a96';
				ctx.fill();
			});
		const validPath = path.filter((p) => p.length === 3);
		validPath.slice(1).forEach((p, i) => line(validPath[i] as Vec3, p as Vec3, '#a16d43'));
		if (point?.length === 3) {
			line(point as Vec3, [point[0], point[1], floor], '#ac8665', [2, 4]);
			const p = project(point as Vec3);
			ctx.beginPath();
			ctx.arc(p[0], p[1], 6, 0, Math.PI * 2);
			ctx.fillStyle = '#a56736';
			ctx.fill();
			ctx.strokeStyle = '#fff';
			ctx.lineWidth = 2;
			ctx.stroke();
			ctx.font = '500 13px sans-serif';
			ctx.textAlign = 'left';
			ctx.lineWidth = 4;
			ctx.strokeStyle = '#f1f7f8';
			ctx.strokeText(you, p[0] + 12, p[1] - 10);
			ctx.fillStyle = '#684627';
			ctx.fillText(you, p[0] + 12, p[1] - 10);
		}
	}
</script>

<figure class="ocean" aria-label={label}>
	<div class="chart-heading">
		<div>
			<h2>{m.ocean_title()}</h2>
			<p>{m.ocean_gesture()}</p>
		</div>
		{#if position?.length === 3}<dl class="vector">
				{#each axes as axis, i (axis)}<div>
						<dt>{axis}</dt>
						<dd>{signed(position[i])}</dd>
					</div>{/each}
			</dl>{/if}
	</div>
	<div class="viewport">
		<canvas
			bind:this={canvas}
			style:height={`${height}px`}
			aria-label={label}
			data-testid="ocean-3d">{m.ocean_canvas_fallback()}</canvas
		>
		{#if unavailable}<p role="status">{m.ocean_canvas_fallback()}</p>{/if}
	</div>
	<div class="tools" aria-label={m.ocean_controls()} role="group">
		<div class="tool-group">
			<button
				type="button"
				onclick={() => turn(-0.2, 0)}
				aria-label={m.ocean_left()}
				title={m.ocean_left()}><ArrowLeft size={17} /></button
			>
			<button
				type="button"
				onclick={() => turn(0.2, 0)}
				aria-label={m.ocean_right()}
				title={m.ocean_right()}><ArrowRight size={17} /></button
			>
			<button
				type="button"
				onclick={() => turn(0, 0.2)}
				aria-label={m.ocean_up()}
				title={m.ocean_up()}><ArrowUp size={17} /></button
			>
			<button
				type="button"
				onclick={() => turn(0, -0.2)}
				aria-label={m.ocean_down()}
				title={m.ocean_down()}><ArrowDown size={17} /></button
			>
		</div>
		<div class="tool-group">
			<button
				type="button"
				onclick={() => enlarge(1.2)}
				aria-label={m.ocean_zoom_in()}
				title={m.ocean_zoom_in()}
				disabled={magnification >= 3}><Plus size={17} /></button
			>
			<button
				type="button"
				onclick={() => enlarge(1 / 1.2)}
				aria-label={m.ocean_zoom_out()}
				title={m.ocean_zoom_out()}
				disabled={magnification <= 0.6}><Minus size={17} /></button
			>
			<button type="button" onclick={reset} aria-label={m.ocean_reset()} title={m.ocean_reset()}
				><RotateCcw size={17} /></button
			>
		</div>
	</div>
	<figcaption>
		<div class="layers">
			{#if own}<label
					><input type="checkbox" bind:checked={showUncertainty} />{m.ocean_uncertainty()}</label
				>{/if}
			{#if map?.seas?.regions.length}<label
					><input type="checkbox" bind:checked={showSeas} />{m.ocean_boundaries()}</label
				>{/if}
		</div>
		{#if map?.seas?.regions.length}
			<ul class="sea-legend">
				{#each map.seas.regions as sea, i (sea.lineage_id)}<li>
						<span style:background={palette[i % palette.length]}></span>{sea.lineage_id}
					</li>{/each}
			</ul>
			<p>{m.ocean_boundary_note()}</p>
		{:else}<p>{m.ocean_no_seas()}</p>{/if}
		{#if own}<p>{m.ocean_uncertainty_note()}</p>{/if}
		{#if meanSea}<p class="membership">
				{meanSea.lineage_id ? m.ocean_inside({ region: meanSea.lineage_id }) : m.ocean_transition()}
			</p>{/if}
		<details>
			<summary>{m.ocean_coordinates_help()}</summary>
			<p>{m.ocean_axes_note()}</p>
			{#if own?.intervals}<dl class="intervals">
					{#each own.intervals as interval, i (i)}<div>
							<dt>{axes[i]}</dt>
							<dd>{signed(interval[0])} … {signed(interval[1])}</dd>
						</div>{/each}
				</dl>
				<p>{m.ocean_intervals_note()}</p>{/if}
		</details>
	</figcaption>
</figure>

<style>
	.ocean {
		width: 100%;
		min-width: 0;
		color: var(--color-ink);
		background: var(--color-mist);
		border-radius: 12px;
		padding: 22px;
	}
	.chart-heading {
		display: flex;
		justify-content: space-between;
		align-items: start;
		gap: 20px;
	}
	h2 {
		font-size: 20px;
		font-weight: 500;
	}
	.chart-heading p,
	figcaption {
		font-size: 12px;
		color: var(--color-body);
		line-height: 1.8;
	}
	.chart-heading p {
		margin-top: 6px;
	}
	.vector {
		display: flex;
		gap: 22px;
		font-variant-numeric: tabular-nums;
	}
	.vector dt {
		font-size: 11px;
		color: var(--color-muted);
	}
	.vector dd {
		font-size: 19px;
	}
	.viewport {
		width: 100%;
	}
	canvas {
		display: block;
		width: 100%;
		cursor: grab;
		touch-action: none;
	}
	canvas:active {
		cursor: grabbing;
	}
	.tools {
		display: flex;
		justify-content: center;
		flex-wrap: wrap;
		gap: 16px;
		margin: 0 0 22px;
	}
	.tool-group {
		display: flex;
		gap: 2px;
	}
	button {
		width: 40px;
		height: 40px;
		display: grid;
		place-items: center;
		border: 1px solid var(--color-line);
		border-radius: 50%;
		color: var(--color-ocean);
		background: var(--color-foam, #f7fafa);
		cursor: pointer;
	}
	button:hover {
		background: #deebed;
	}
	button:focus-visible,
	summary:focus-visible {
		outline: 2px solid var(--color-ocean);
		outline-offset: 3px;
	}
	button:disabled {
		opacity: 0.4;
		cursor: default;
	}
	figcaption {
		border-top: 1px solid var(--color-line);
		padding-top: 16px;
	}
	.layers {
		display: flex;
		flex-wrap: wrap;
		gap: 20px;
		margin-bottom: 12px;
	}
	label {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
	}
	input {
		accent-color: var(--color-ocean);
		color: var(--color-ocean);
	}
	.sea-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 20px;
		margin-bottom: 8px;
		overflow-wrap: anywhere;
	}
	.sea-legend li {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.sea-legend span {
		display: inline-block;
		flex-shrink: 0;
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}
	.membership {
		margin-top: 10px;
		color: var(--color-ink);
		font-weight: 500;
		overflow-wrap: anywhere;
	}
	details {
		margin-top: 12px;
	}
	summary {
		cursor: pointer;
		text-decoration: underline;
		text-underline-offset: 4px;
	}
	details p {
		max-width: 65ch;
		margin-top: 10px;
	}
	.intervals {
		display: flex;
		flex-wrap: wrap;
		gap: 20px;
		margin-top: 10px;
		font-variant-numeric: tabular-nums;
	}
	.intervals div {
		display: flex;
		gap: 8px;
	}
	@media (max-width: 540px) {
		.ocean {
			padding: 16px 10px;
		}
		.chart-heading {
			flex-direction: column;
			gap: 14px;
		}
		.vector {
			gap: 30px;
		}
		h2 {
			font-size: 18px;
		}
		.tools {
			gap: 8px;
		}
		button {
			width: 36px;
			height: 36px;
		}
	}
</style>

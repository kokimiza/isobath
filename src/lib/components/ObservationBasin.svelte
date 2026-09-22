<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import MoveUpRight from '@lucide/svelte/icons/move-up-right';

	// An authored mathematical contour study, never passed off as an observed chart.
	const levels = Array.from({ length: 22 }, (_, level) => {
		const radius = 445 - level * 17;
		const points = Array.from({ length: 161 }, (_, i) => {
			const angle = (i / 160) * Math.PI * 2;
			const shape =
				1 + 0.11 * Math.sin(angle * 3 + 0.8) + 0.055 * Math.cos(angle * 5 + level * 0.045);
			const x = 356 + Math.cos(angle) * radius * shape;
			const y = 296 + Math.sin(angle) * radius * 0.77 * shape;
			return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
		}).join(' ');
		return {
			path: `${points}Z`,
			color: `hsl(${194 + level * 0.75} ${43 + level * 0.5}% ${76 - level * 2.55}%)`,
		};
	});
	let point = $state({ x: 339, y: 273 });
	function move(event: PointerEvent) {
		if (event.pointerType === 'touch') return;
		const box = event.currentTarget as HTMLButtonElement;
		const rect = box.getBoundingClientRect();
		point = {
			x: Math.max(45, Math.min(595, ((event.clientX - rect.left) / rect.width) * 640)),
			y: Math.max(60, Math.min(455, ((event.clientY - rect.top) / rect.height) * 520)),
		};
	}
	function keyboard(event: KeyboardEvent) {
		const directions: Record<string, [number, number]> = {
			ArrowLeft: [-20, 0],
			ArrowRight: [20, 0],
			ArrowUp: [0, -20],
			ArrowDown: [0, 20],
		};
		const direction = directions[event.key];
		if (!direction) return;
		event.preventDefault();
		point = {
			x: Math.max(45, Math.min(595, point.x + direction[0])),
			y: Math.max(60, Math.min(455, point.y + direction[1])),
		};
	}
</script>

<figure class="basin-figure">
	<button
		class="basin"
		type="button"
		aria-label={m.landing_map_control()}
		aria-describedby="basin-description"
		onpointermove={move}
		onkeydown={keyboard}
		onclick={() => (point = { x: point.x > 350 ? 230 : 430, y: point.y > 280 ? 190 : 350 })}
	>
		<svg viewBox="0 0 640 520" preserveAspectRatio="none" aria-hidden="true">
			<rect width="640" height="520" fill="#d9ebea" />
			{#each levels as level, i (i)}
				<path
					d={level.path}
					fill={level.color}
					stroke="#e2f5ee"
					stroke-opacity={i % 3 === 0 ? 0.47 : 0.21}
					stroke-width="0.8"
				/>
			{/each}
			<g stroke="#effcf9" stroke-width="0.6" opacity="0.18">
				{#each [80, 160, 240, 320, 400, 480, 560] as x (x)}<path d={`M${x} 0V520`} />{/each}
				{#each [80, 160, 240, 320, 400, 480] as y (y)}<path d={`M0 ${y}H640`} />{/each}
			</g>
			<g class="observation-point" transform={`translate(${point.x},${point.y})`}>
				<path d="M-18 0H18M0-18V18" stroke="#fff" stroke-width="1" opacity="0.65" />
				<circle r="11" fill="none" stroke="#fff" stroke-opacity="0.6" />
				<circle r="3.5" fill="#fff" />
			</g>
		</svg>
		<span class="basin-label"
			>{m.landing_map_point()}<MoveUpRight size={15} strokeWidth={1.4} aria-hidden="true" /></span
		>
		<span class="basin-bottom">ISOBATH</span>
	</button>
	<figcaption id="basin-description">
		<span>{m.landing_map_caption()}</span>
		<span class="explanation">{m.landing_map_disclaimer()}</span>
		<span class="sr-only">{m.landing_map_hint()} {m.landing_map_keyboard()}</span>
	</figcaption>
</figure>

<style>
	.basin-figure {
		margin: 0;
		min-width: 0;
	}
	.basin {
		display: block;
		position: relative;
		width: 100%;
		aspect-ratio: 640 / 520;
		overflow: hidden;
		border-radius: 48% 48% 18px 18px / 32% 32% 18px 18px;
		background: #d9ebea;
		padding: 0;
		border: 0;
		cursor: crosshair;
	}
	svg {
		width: 100%;
		height: 100%;
		display: block;
	}
	.basin-label {
		position: absolute;
		inset: auto 24px 26px auto;
		display: flex;
		gap: 12px;
		align-items: center;
		font-size: 12px;
		color: white;
		background: #174962;
		border-radius: 30px;
		padding: 9px 16px;
	}
	.basin-bottom {
		position: absolute;
		bottom: 27px;
		left: 26px;
		color: #effbf7;
		font-size: 13px;
		letter-spacing: 0.16em;
	}
	.observation-point {
		transition: transform 650ms cubic-bezier(0.16, 1, 0.3, 1);
	}
	figcaption {
		padding-top: 16px;
		color: var(--color-muted);
		font-size: 11px;
		line-height: 1.9;
		display: flex;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
	}
	.explanation {
		font-size: 10px;
	}
	@media (max-width: 640px) {
		.basin {
			border-radius: 44% 44% 12px 12px / 28% 28% 12px 12px;
		}
		.basin-label {
			bottom: 20px;
			right: 16px;
			font-size: 10px;
		}
		.basin-bottom {
			left: 18px;
			bottom: 24px;
			font-size: 11px;
		}
		figcaption {
			gap: 2px;
		}
	}
</style>

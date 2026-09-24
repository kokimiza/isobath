import { describe, expect, it } from 'vitest';
import { isosurface, rotate, hpdThreshold } from './geometry';

describe('three-dimensional chart geometry', () => {
	it('extracts the actual Z boundary rather than a flat XY contour', () => {
		const axes = [
			[-1, 1],
			[-1, 1],
			[-1, 1],
		];
		const field = axes[0].flatMap(() => axes[1].flatMap(() => axes[2]));
		const mesh = isosurface(axes, field, 0.25);
		expect(mesh.length).toBeGreaterThan(0);
		for (const point of mesh.flat()) expect(point[2]).toBeCloseTo(0.25);
	});
	it('rotation retains depth and preserves distances', () => {
		const point = rotate([1, -2, 3], 0.7, 0.4);
		expect(point.reduce((sum, value) => sum + value ** 2, 0)).toBeCloseTo(14);
		expect(rotate([0, 0, 2], 0.7, 0.4)[1]).not.toBe(rotate([0, 0, -2], 0.7, 0.4)[1]);
	});
	it('uses cumulative probability for the HPD surface', () => {
		expect(hpdThreshold([0.1, 0.2, 0.7], 0.8)).toBe(0.2);
		expect(
			isosurface(
				[
					[0, 1],
					[0, 1],
					[0, 1],
				],
				[0],
				0.5,
			),
		).toEqual([]);
	});
});

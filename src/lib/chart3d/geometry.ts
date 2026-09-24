/** Isosurfaces of a genuine 3-D scalar field, using a consistent tetrahedral grid. */
export type Vec3 = [number, number, number];
export type Triangle = [Vec3, Vec3, Vec3];
const corners = [
	[0, 0, 0],
	[1, 0, 0],
	[0, 1, 0],
	[1, 1, 0],
	[0, 0, 1],
	[1, 0, 1],
	[0, 1, 1],
	[1, 1, 1],
];
const tetrahedra = [
	[0, 1, 3, 7],
	[0, 3, 2, 7],
	[0, 2, 6, 7],
	[0, 6, 4, 7],
	[0, 4, 5, 7],
	[0, 5, 1, 7],
];

export function isosurface(axes: number[][], values: number[], level: number): Triangle[] {
	const [nx, ny, nz] = axes.map((a) => a.length);
	if (values.length !== nx * ny * nz || !values.every(Number.isFinite)) return [];
	const triangles: Triangle[] = [];
	for (let x = 0; x < nx - 1; x++)
		for (let y = 0; y < ny - 1; y++)
			for (let z = 0; z < nz - 1; z++) {
				const points = corners.map(
					([dx, dy, dz]) => [axes[0][x + dx], axes[1][y + dy], axes[2][z + dz]] as Vec3,
				);
				const v = corners.map(
					([dx, dy, dz]) => values[(x + dx) * ny * nz + (y + dy) * nz + z + dz],
				);
				if (v.every((a) => a < level) || v.every((a) => a >= level)) continue;
				const edge = (a: number, b: number): Vec3 => {
					const t = (level - v[a]) / (v[b] - v[a]);
					return points[a].map((p, d) => p + t * (points[b][d] - p)) as Vec3;
				};
				for (const tetra of tetrahedra) {
					const inside = tetra.filter((i) => v[i] >= level),
						outside = tetra.filter((i) => v[i] < level);
					if (inside.length === 1)
						triangles.push(outside.map((j) => edge(inside[0], j)) as Triangle);
					else if (inside.length === 3)
						triangles.push(inside.map((i) => edge(i, outside[0])) as Triangle);
					else if (inside.length === 2) {
						const [a, b] = inside,
							[c, d] = outside;
						triangles.push(
							[edge(a, c), edge(a, d), edge(b, c)],
							[edge(a, d), edge(b, d), edge(b, c)],
						);
					}
				}
			}
	return triangles;
}

export function hpdThreshold(values: number[], probability: number): number {
	const sorted = [...values].sort((a, b) => b - a);
	const target = probability * sorted.reduce((a, b) => a + b, 0);
	let sum = 0;
	for (const value of sorted) {
		sum += value;
		if (sum >= target) return value;
	}
	return sorted.at(-1) ?? 0;
}

export function rotate([x, y, z]: Vec3, yaw: number, pitch: number): Vec3 {
	const horizontal = Math.cos(yaw) * x - Math.sin(yaw) * y;
	const depth = Math.sin(yaw) * x + Math.cos(yaw) * y;
	return [
		horizontal,
		Math.sin(pitch) * depth - Math.cos(pitch) * z,
		Math.cos(pitch) * depth + Math.sin(pitch) * z,
	];
}

export const signed = (value: number) => `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(2)}`;

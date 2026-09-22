import { paraglideVitePlugin } from '@inlang/paraglide-js';
import tailwindcss from '@tailwindcss/vite';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import { playwright } from '@vitest/browser-playwright';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';

// ssr=false pages render no links, so the crawler cannot reach their /en variants.
// ponytail: listed by hand; generate from src/routes if the route count grows.
// kit's CSP HostSource template type; env values are plain strings
type HostSource = `${string}://${string}.${string}`;

const EN_ROUTES = [
	'/legal/terms',
	'/legal/privacy',
	'/legal/research',
	'/legal/data-retention',
	'',
	'/status',
	'/auth/login',
	'/auth/signup',
	'/auth/callback',
	'/consent',
	'/profile',
	'/settings',
	'/survey/initial',
	'/survey',
	'/journey',
	'/chart',
];

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), 'PUBLIC_');
	return {
		plugins: [
			tailwindcss(),
			sveltekit({
				compilerOptions: {
					// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
					runes: ({ filename }) =>
						filename.split(/[/\\]/).includes('node_modules') ? undefined : true,
				},
				adapter: adapter(),
				prerender: { entries: ['*', ...EN_ROUTES.map((r) => `/en${r}` as const)] },
				// SEC-FE-01: hashes of inline scripts are added to a <meta> CSP on prerendered pages
				csp: {
					mode: 'hash',
					directives: {
						'default-src': ['self'],
						'script-src': ['self'],
						'connect-src': [
							'self',
							env.PUBLIC_API_BASE as HostSource,
							env.PUBLIC_SUPABASE_URL as HostSource,
						],
						'img-src': ['self', 'data:'],
						'style-src': ['self', 'unsafe-inline'],
						'object-src': ['none'],
						'base-uri': ['self'],
						'form-action': ['self'],
					},
				},
			}),

			paraglideVitePlugin({
				project: './project.inlang',
				outdir: './src/lib/paraglide',
				emitTsDeclarations: true,
				// prerendered static pages: the locale must come from the URL (/en/...), not a cookie
				strategy: ['url', 'baseLocale'],
			}),
		],
		test: {
			expect: { requireAssertions: true },
			projects: [
				{
					extends: './vite.config.ts',
					test: {
						name: 'client',
						browser: {
							enabled: true,
							provider: playwright(),
							instances: [{ browser: 'chromium', headless: true }],
						},
						include: ['src/**/*.svelte.{test,spec}.{js,ts}'],
						exclude: ['src/lib/server/**'],
					},
				},

				{
					extends: './vite.config.ts',
					test: {
						name: 'server',
						environment: 'node',
						include: ['src/**/*.{test,spec}.{js,ts}'],
						exclude: ['src/**/*.svelte.{test,spec}.{js,ts}'],
					},
				},
			],
		},
	};
});

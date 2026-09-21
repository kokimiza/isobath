/** @type {import('prettier').Config} */
export default {
	useTabs: true,
	singleQuote: true,
	trailingComma: 'all', // Prettier 3 default: one-line diffs when appending
	printWidth: 100, // same as Ruff (app/pyproject.toml)
	endOfLine: 'lf',
	plugins: ['prettier-plugin-svelte', 'prettier-plugin-tailwindcss'],
	tailwindStylesheet: './src/routes/layout.css',
	overrides: [
		{ files: '*.svelte', options: { parser: 'svelte' } },
		// prose: never re-wrap Japanese text
		{ files: '*.md', options: { proseWrap: 'preserve', useTabs: false } },
	],
};

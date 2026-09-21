import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import { defineConfig, includeIgnoreFile } from 'eslint/config';
import globals from 'globals';
import path from 'node:path';
import ts from 'typescript-eslint';

const gitignore = path.resolve(import.meta.dirname, '.gitignore');

export default defineConfig(
	includeIgnoreFile(gitignore),
	{ ignores: ['app/', 'supabase/', 'doc/', 'project.inlang/', 'static/'] },

	js.configs.recommended,
	ts.configs.recommendedTypeChecked,
	ts.configs.stylisticTypeChecked,
	svelte.configs.recommended,
	prettier,
	svelte.configs.prettier,

	{
		languageOptions: {
			globals: { ...globals.browser, ...globals.node },
			parserOptions: {
				// type-aware linting via the TS project service; root config files use the default project
				projectService: { allowDefaultProject: ['*.js'] },
				tsconfigRootDir: import.meta.dirname,
				extraFileExtensions: ['.svelte'],
			},
		},
		linterOptions: { reportUnusedDisableDirectives: 'error' },
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: { parserOptions: { parser: ts.parser } },
	},
	{
		// typescript-eslint cannot see types across .svelte imports / generated $types;
		// svelte-check (pnpm check) is the type authority for components.
		files: ['**/*.svelte'],
		rules: {
			'@typescript-eslint/no-unsafe-assignment': 'off',
			'@typescript-eslint/no-unsafe-call': 'off',
			'@typescript-eslint/no-unsafe-member-access': 'off',
			'@typescript-eslint/no-unsafe-argument': 'off',
			'@typescript-eslint/no-unsafe-return': 'off',
		},
	},

	{
		rules: {
			// TypeScript already reports undefined names (typescript-eslint FAQ)
			'no-undef': 'off',
			eqeqeq: ['error', 'smart'],
			'no-console': ['warn', { allow: ['warn', 'error'] }],
			'object-shorthand': 'error',
			'prefer-template': 'error',

			'@typescript-eslint/consistent-type-imports': [
				'error',
				{ prefer: 'type-imports', fixStyle: 'inline-type-imports' },
			],
			'@typescript-eslint/no-import-type-side-effects': 'error',
			'@typescript-eslint/switch-exhaustiveness-check': 'error',
			'@typescript-eslint/no-unused-vars': [
				'error',
				{ argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
			],

			'svelte/block-lang': ['error', { script: 'ts' }],
			'svelte/button-has-type': 'error',
			'svelte/no-target-blank': 'error',
			'svelte/require-event-prefix': 'error',
			// All internal links/goto go through href() in $lib/nav, which calls resolve() and
			// adds the locale prefix. The rule only recognises a literal resolve() call.
			'svelte/no-navigation-without-resolve': ['error', { ignoreLinks: true, ignoreGoto: true }],
		},
	},
	{
		// config files: plain JS without project types
		files: ['*.config.js', '*.config.ts'],
		extends: [ts.configs.disableTypeChecked],
	},
);

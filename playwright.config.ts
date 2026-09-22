import { defineConfig } from '@playwright/test';

export default defineConfig({
	webServer: {
		command: 'npm run build && npm run preview',
		port: 4173,
		// Every service request is intercepted by the tests. Never contact real accounts.
		env: {
			PUBLIC_API_BASE: 'http://127.0.0.1:18000',
			PUBLIC_SUPABASE_URL: 'http://127.0.0.1:18001',
			PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'test-publishable-key',
		},
	},
	use: { baseURL: 'http://localhost:4173' },
	testMatch: '**/*.e2e.{ts,js}',
});

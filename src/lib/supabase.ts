import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { PUBLIC_SUPABASE_PUBLISHABLE_KEY, PUBLIC_SUPABASE_URL } from '$env/static/public';

// Auth only. The app never queries tables through supabase-js (design D-1).
let client: SupabaseClient | undefined;

/** Browser-only: created lazily so prerendering never touches auth storage. */
export function supabase(): SupabaseClient {
	client ??= createClient(PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_PUBLISHABLE_KEY, {
		auth: { flowType: 'pkce', detectSessionInUrl: false, persistSession: true },
	});
	return client;
}

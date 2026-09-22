import { redirect } from '@sveltejs/kit';
import { safeNext } from '$lib/auth.svelte';
import { href } from '$lib/nav';
import { supabase } from '$lib/supabase';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url }) => {
	const { data } = await supabase().auth.getSession();
	if (data.session) redirect(307, safeNext(url.searchParams.get('next')) ?? href('/survey'));
};

import { redirect } from '@sveltejs/kit';
import { safeNext } from '$lib/auth.svelte';
import { href } from '$lib/nav';
import { loadRegistration } from '$lib/registration';
import { supabase } from '$lib/supabase';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url }) => {
	const next = safeNext(url.searchParams.get('next')) ?? href('/survey');
	if ((await supabase().auth.getSession()).data.session) redirect(307, next);
	if (!loadRegistration()) redirect(307, href('/auth/signup', { next }));
	return { next };
};

import { redirect } from '@sveltejs/kit';
import { href } from '$lib/nav';
import { supabase } from '$lib/supabase';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ url }) => {
	const { data } = await supabase().auth.getSession();
	if (!data.session) redirect(307, href('/auth/login', { next: url.pathname }));
	return { session: data.session };
};

import { error, redirect } from '@sveltejs/kit';
import { apiErrorMessage } from '$lib/api.svelte';
import { ensureConsent } from '$lib/consent';
import { href } from '$lib/nav';
import { supabase } from '$lib/supabase';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ url, route }) => {
	const { data } = await supabase().auth.getSession();
	const next = url.pathname + url.search;
	// Every "participate" link points at /survey: newcomers must see the pre-account
	// consent and research questions first; returning users follow its login link.
	if (!data.session)
		redirect(
			307,
			href(route.id?.startsWith('/(client)/(app)/survey') ? '/auth/signup' : '/auth/login', {
				next,
			}),
		);
	// Layout components survive navigation. Resolve the guard before rendering,
	// so a redirect to /consent cannot strand its children behind a loading flag.
	// Account controls must remain available even before consent is given.
	if (!['/(client)/(app)/consent', '/(client)/(app)/settings'].includes(route.id ?? '')) {
		let consented: boolean;
		try {
			consented = await ensureConsent(data.session);
		} catch (e) {
			error(503, apiErrorMessage(e));
		}
		if (!consented) redirect(307, href('/consent', { next }));
	}
	return { session: data.session };
};

import { resolve } from '$app/paths';
import type { Pathname } from '$app/types';
import { localizeHref } from '$lib/paraglide/runtime';

/** Typed route -> base-path-aware, locale-prefixed href. */
export function href(path: Pathname, query?: Record<string, string>): string {
	const url = localizeHref(resolve(path));
	return query ? `${url}?${new URLSearchParams(query)}` : url;
}

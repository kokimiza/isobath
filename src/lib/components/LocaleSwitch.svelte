<script lang="ts">
	import Languages from '@lucide/svelte/icons/languages';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { getLocale, locales, localizeHref, type Locale } from '$lib/paraglide/runtime';

	const localeName: Record<Locale, () => string> = {
		ja: m.locale_name_ja,
		en: m.locale_name_en,
	};

	// two locales: the button toggles to the other one
	const target = $derived(locales.find((l) => l !== getLocale()) ?? getLocale());
</script>

<!-- A link, not a <button>: it navigates, works without JS and lets the prerender crawler reach /en.
     Full reload because paraglide messages are resolved per page load. -->
<a
	href={localizeHref(page.url.pathname, { locale: target })}
	hreflang={target}
	lang={target}
	aria-label={m.locale_switch_label({ language: localeName[target]() })}
	title={m.locale_switch_label({ language: localeName[target]() })}
	class="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-2.5 py-1.5 text-slate-300 transition hover:border-cyan-300 hover:text-cyan-300 focus-visible:outline-2 focus-visible:outline-cyan-300"
	data-sveltekit-reload
>
	<Languages class="size-4" aria-hidden="true" />
	<span>{localeName[target]()}</span>
</a>

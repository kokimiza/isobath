<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { getLocale, locales, localizeHref, type Locale } from '$lib/paraglide/runtime';
	import { auth, startAuth } from '$lib/auth.svelte';
	import { net } from '$lib/api.svelte';
	import { href } from '$lib/nav';
	import favicon from '$lib/assets/favicon.svg';
	import './layout.css';

	let { children } = $props();

	const localeName: Record<Locale, () => string> = {
		ja: m.locale_name_ja,
		en: m.locale_name_en,
	};

	onMount(startAuth);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>{m.site_name()}</title>
	<meta name="description" content={m.site_tagline()} />
</svelte:head>

<div class="flex min-h-dvh flex-col bg-slate-950 text-slate-100">
	<header class="border-b border-slate-800">
		<nav class="mx-auto flex max-w-3xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 text-sm">
			<a href={href('/')} class="font-semibold tracking-wide text-cyan-300">{m.site_name()}</a>
			<div class="ml-auto flex items-center gap-4">
				{#if auth.session}
					<a href={href('/profile')} class="hover:text-cyan-300">{m.nav_profile()}</a>
					<a href={href('/settings')} class="hover:text-cyan-300">{m.nav_settings()}</a>
				{:else if auth.ready}
					<a href={href('/auth/login')} class="hover:text-cyan-300">{m.nav_login()}</a>
				{/if}
				<ul class="flex gap-2 text-slate-400" aria-label={m.nav_language()}>
					{#each locales as locale (locale)}
						<li>
							<a
								href={localizeHref(page.url.pathname, { locale })}
								hreflang={locale}
								aria-current={locale === getLocale() ? 'true' : undefined}
								class="hover:text-cyan-300 aria-[current]:text-slate-100"
								data-sveltekit-reload>{localeName[locale]()}</a
							>
						</li>
					{/each}
				</ul>
			</div>
		</nav>
	</header>

	{#if net.slow}
		<p role="status" class="bg-cyan-950 px-4 py-2 text-center text-sm text-cyan-200">
			{m.ship_starting()}
		</p>
	{/if}

	<main class="mx-auto w-full max-w-3xl flex-1 px-4 py-10">
		{@render children()}
	</main>

	<footer class="border-t border-slate-800 px-4 py-6 text-center text-xs text-slate-500">
		{m.footer_non_diagnostic()}
	</footer>
</div>

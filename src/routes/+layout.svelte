<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { auth, startAuth } from '$lib/auth.svelte';
	import { net } from '$lib/api.svelte';
	import { href } from '$lib/nav';
	import LocaleSwitch from '$lib/components/LocaleSwitch.svelte';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import favicon from '$lib/assets/favicon.svg';
	import Waves from '@lucide/svelte/icons/waves';
	import './layout.css';

	let { children } = $props();

	onMount(startAuth);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>{m.site_name()}</title>
	<meta name="description" content={m.site_tagline()} />
</svelte:head>

<div class="flex min-h-dvh flex-col bg-paper text-ink">
	<a class="skip-link" href="#main">{m.skip_content()}</a>
	<header class="site-header">
		<nav class="site-nav" aria-label={m.footer_col_service()}>
			<a href={href('/')} class="brand" aria-label={m.site_name()}>
				<Waves size={30} strokeWidth={1.4} aria-hidden="true" />
				<span class="brand-word">ISOBATH</span><span class="brand-name">{m.brand_descriptor()}</span
				>
			</a>
			<div class="nav-links">
				<a
					href={href('/chart')}
					aria-current={page.route.id === '/chart' ? 'page' : undefined}
					class="hover:text-ocean aria-[current=page]:text-ocean">{m.nav_chart()}</a
				>
				{#if auth.session}
					<a
						href={href('/profile')}
						aria-current={page.route.id?.startsWith('/(client)/(app)') ? 'page' : undefined}
						class="hover:text-ocean aria-[current=page]:text-ocean">{m.nav_my_page()}</a
					>
				{:else}
					<a href={href('/auth/login')} class="hover:text-ocean">{m.nav_login()}</a>
				{/if}
				<LocaleSwitch />
			</div>
		</nav>
	</header>

	{#if net.slow}
		<p role="status" class="bg-mist px-4 py-2 text-center text-sm text-ocean">
			{m.ship_starting()}
		</p>
	{/if}

	<main
		id="main"
		class="page-main"
		class:landing-main={page.route.id === '/'}
		class:auth-main={(page.route.id ?? '').includes('/auth/') || (page.route.id ?? '').endsWith('/consent')}
	>
		{@render children()}
	</main>

	<SiteFooter />
</div>

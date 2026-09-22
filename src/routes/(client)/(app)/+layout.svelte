<script lang="ts">
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';

	let { children } = $props();
	const tabs = $derived([
		{
			path: '/profile',
			label: m.nav_overview(),
			active:
				(page.route.id ?? '').endsWith('/profile') || (page.route.id ?? '').includes('/survey'),
		},
		{ path: '/journey', label: m.nav_journey(), active: page.route.id?.endsWith('/journey') },
		{ path: '/settings', label: m.nav_settings(), active: page.route.id?.endsWith('/settings') },
	] as const);
</script>

{#if page.route.id !== '/(client)/(app)/consent'}
	<nav
		aria-label={m.nav_my_page()}
		class="mb-8 flex flex-wrap gap-2 border-b border-slate-800 pb-4 text-sm"
	>
		{#each tabs as item (item.path)}
			<a
				href={href(item.path)}
				aria-current={item.active ? 'page' : undefined}
				class="rounded-md px-4 py-2 text-slate-400 hover:text-cyan-300 aria-[current=page]:bg-slate-800 aria-[current=page]:text-cyan-300"
				>{item.label}</a
			>
		{/each}
	</nav>
{/if}

{@render children()}

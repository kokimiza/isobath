<script lang="ts">
	import Waves from '@lucide/svelte/icons/waves';
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';

	interface FooterLink {
		href: string;
		label: () => string;
	}

	const columns: { heading: () => string; links: FooterLink[] }[] = [
		{
			heading: m.footer_col_service,
			links: [
				{ href: href('/'), label: m.nav_home },
				{ href: href('/auth/signup'), label: m.nav_signup },
				{ href: href('/status'), label: m.status_title },
			],
		},
		{
			heading: m.footer_col_research,
			links: [
				{ href: href('/legal/research'), label: m.legal_research },
				{ href: href('/legal/data-retention'), label: m.legal_data_retention },
			],
		},
		{
			heading: m.footer_col_legal,
			links: [
				{ href: href('/legal/terms'), label: m.legal_terms },
				{ href: href('/legal/privacy'), label: m.legal_privacy },
				{ href: `${href('/legal/privacy')}#processors`, label: m.legal_processors },
				{ href: `${href('/legal/privacy')}#rights`, label: m.legal_rights },
			],
		},
	];

	const year = new Date().getFullYear(); // fixed at prerender time
</script>

<footer class="mt-16 border-t border-cyan-900/60 bg-slate-900">
	<div
		class="mx-auto grid max-w-5xl gap-10 px-6 py-14 sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(3,1fr)]"
	>
		<div class="space-y-4">
			<a
				href={href('/')}
				class="inline-flex items-center gap-2 text-lg font-semibold text-cyan-300"
			>
				<Waves class="size-5" aria-hidden="true" />
				{m.site_name()}
			</a>
			<p class="text-sm leading-relaxed text-slate-400">{m.site_tagline()}</p>
			<p class="text-xs leading-relaxed text-slate-500">{m.footer_non_diagnostic()}</p>
		</div>

		{#each columns as column, i (i)}
			<nav aria-label={column.heading()}>
				<h2 class="text-xs font-semibold tracking-widest text-slate-500 uppercase">
					{column.heading()}
				</h2>
				<ul class="mt-4 space-y-3 text-sm">
					{#each column.links as link (link.href)}
						<li>
							<a href={link.href} class="text-slate-300 transition hover:text-cyan-300">
								{link.label()}
							</a>
						</li>
					{/each}
				</ul>
			</nav>
		{/each}
	</div>

	<div class="border-t border-slate-800">
		<p class="mx-auto max-w-5xl px-6 py-5 text-xs text-slate-500">
			{m.footer_copyright({ year })}
		</p>
	</div>
</footer>

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
				{ href: href('/chart'), label: m.nav_chart },
				{ href: href('/survey'), label: m.nav_signup },
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

<footer class="mt-16 border-t border-line bg-mist">
	<div
		class="mx-auto grid max-w-[1328px] gap-10 px-6 py-14 sm:grid-cols-2 sm:px-10 lg:grid-cols-[1.6fr_repeat(3,1fr)]"
	>
		<div class="space-y-4">
			<a href={href('/')} class="inline-flex items-center gap-2 text-lg font-semibold text-ocean">
				<Waves class="size-5" aria-hidden="true" />
				{m.site_name()}
			</a>
			<p class="max-w-72 text-sm leading-loose text-body">{m.site_tagline()}</p>
			<p class="max-w-80 text-xs leading-loose text-muted">{m.footer_non_diagnostic()}</p>
		</div>

		{#each columns as column, i (i)}
			<nav aria-label={column.heading()}>
				<h2 class="text-xs font-semibold tracking-widest text-muted uppercase">
					{column.heading()}
				</h2>
				<ul class="mt-4 space-y-3 text-sm">
					{#each column.links as link (link.href)}
						<li>
							<a href={link.href} class="text-body transition hover:text-ocean">
								{link.label()}
							</a>
						</li>
					{/each}
				</ul>
			</nav>
		{/each}
	</div>

	<div class="border-t border-line">
		<p class="mx-auto max-w-[1328px] px-6 py-5 text-xs text-muted sm:px-10">
			{m.footer_copyright({ year })}
		</p>
	</div>
</footer>

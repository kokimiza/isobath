<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import { getLocale } from '$lib/paraglide/runtime';

	let { data } = $props();
</script>

<svelte:head>
	<title>{m.page_title({ title: data.title })}</title>
</svelte:head>

{#if getLocale() !== 'ja'}
	<p class="mb-6 rounded-md border border-slate-700 px-4 py-3 text-sm text-slate-300" lang="en">
		{m.legal_japanese_only()}
	</p>
{/if}

<article
	lang="ja"
	class="prose max-w-none prose-invert prose-headings:scroll-mt-20 prose-a:text-cyan-300 prose-blockquote:border-amber-500 prose-blockquote:text-amber-200 prose-blockquote:not-italic prose-table:text-sm"
>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- repository-authored Markdown rendered at build time -->
	{@html data.html}
</article>

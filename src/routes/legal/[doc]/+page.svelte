<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import { getLocale } from '$lib/paraglide/runtime';

	let { data } = $props();
</script>

<svelte:head>
	<title>{m.page_title({ title: data.title })}</title>
</svelte:head>

{#if getLocale() !== 'ja'}
	<p class="mb-6 rounded-md border border-line px-4 py-3 text-sm text-body" lang="en">
		{m.legal_japanese_only()}
	</p>
{/if}

<article
	lang="ja"
	class="prose max-w-none prose-headings:scroll-mt-20 prose-a:text-ocean prose-blockquote:border-line prose-blockquote:text-body prose-blockquote:not-italic prose-table:text-sm"
>
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- repository-authored Markdown rendered at build time -->
	{@html data.html}
</article>

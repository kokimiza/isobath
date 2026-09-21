<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { api, type Meta } from '$lib/api.svelte';
	import { auth } from '$lib/auth.svelte';
	import { stageDescription, stageName } from '$lib/i18n';
	import { href } from '$lib/nav';

	// Prerendered: live numbers are fetched in the browser only.
	let meta = $state<Meta | null>(null);

	onMount(() => {
		api
			.meta()
			.then((v) => (meta = v))
			.catch(() => (meta = null)); // stats are decorative; the page works without the API
	});
</script>

<section class="space-y-6">
	<h1 class="text-3xl leading-snug font-semibold text-balance">
		{m.landing_title()}<br />
		<span class="text-cyan-300">{m.landing_title_2()}</span>
	</h1>
	<p class="leading-relaxed text-slate-300">{m.landing_lead()}</p>

	<div class="flex flex-wrap gap-3">
		{#if auth.session}
			<a href={href('/profile')} class="btn-primary">{m.landing_cta_continue()}</a>
		{:else}
			<a href={href('/auth/signup')} class="btn-primary">{m.landing_cta_signup()}</a>
			<a href={href('/auth/login')} class="btn-secondary">{m.landing_cta_login()}</a>
		{/if}
	</div>
</section>

{#if meta}
	<section class="mt-12 rounded-lg border border-slate-800 p-5">
		<h2 class="text-sm text-slate-400">{m.landing_stage_label()}</h2>
		<p class="mt-1 text-xl font-semibold">{stageName[meta.chart.stage]()}</p>
		<p class="mt-2 text-sm text-slate-300">{stageDescription[meta.chart.stage]()}</p>
		<p class="mt-4 text-sm text-slate-400">
			{m.landing_participants({ count: meta.participants })}
		</p>
	</section>
{/if}

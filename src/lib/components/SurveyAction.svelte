<script lang="ts">
	import type { Position } from '$lib/api.svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';

	let { survey }: { survey?: Position['survey'] } = $props();
</script>

{#if !survey}
	<a href={href('/survey')} class="btn-primary">{m.nav_answer()}</a>
{:else if !survey.initial_completed}
	<a href={href('/survey/initial')} class="btn-primary">
		{survey.open_session ? m.profile_resume_initial() : m.profile_start_initial()}
	</a>
{:else if survey.open_kind === 'continuous'}
	<a href={href('/survey')} class="btn-primary">{m.profile_resume_continuous()}</a>
{:else if survey.continuous_done_today}
	<p class="text-sm text-slate-300" role="status">{m.profile_continuous_done_today()}</p>
{:else}
	<a href={href('/survey')} class="btn-primary">{m.profile_start_continuous()}</a>
{/if}

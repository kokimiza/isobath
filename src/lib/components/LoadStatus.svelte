<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	let {
		pending,
		error,
		onretry,
		label = '',
	}: {
		pending: boolean;
		error: string | null;
		onretry: () => unknown;
		label?: string;
	} = $props();
</script>

{#if pending}
	<p role="status" class="mt-4 text-sm text-muted">{label} {m.common_loading()}</p>
{:else if error}
	<div class="mt-4 space-y-3">
		<p role="alert" class="text-sm text-danger">{label} {error}</p>
		<button type="button" class="btn-secondary" onclick={onretry}>{m.survey_retry()}</button>
	</div>
{/if}

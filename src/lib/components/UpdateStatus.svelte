<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import { formatUpdateTime } from '$lib/i18n';

	let {
		updatedAt,
		nextUpdateAt,
		pending = false,
	}: { updatedAt: string | null; nextUpdateAt: string; pending?: boolean } = $props();

	const next = $derived(formatUpdateTime(nextUpdateAt));
</script>

<div class="space-y-1 text-xs text-muted">
	<p>
		{updatedAt
			? m.update_last({ time: formatUpdateTime(updatedAt) })
			: m.update_never({ time: next })}
	</p>
	{#if pending}
		<p class="text-warning" role="status">{m.update_pending({ time: next })}</p>
	{/if}
	<p>{m.update_schedule()}</p>
</div>

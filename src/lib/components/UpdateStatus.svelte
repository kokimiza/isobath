<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import { formatUpdateTime } from '$lib/i18n';

	let { updatedAt, nextUpdateAt }: { updatedAt: string | null; nextUpdateAt: string } = $props();

	const next = $derived(formatUpdateTime(nextUpdateAt));
</script>

<div class="space-y-1 text-xs text-muted">
	<p>
		{updatedAt
			? m.update_last({ time: formatUpdateTime(updatedAt) })
			: m.update_never({ time: next })}
	</p>
	<p>{m.update_schedule()}</p>
</div>

<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';
</script>

<h1 class="text-2xl font-semibold">{m.status_title()}</h1>
<p class="mt-4 leading-relaxed text-slate-300">{m.status_body()}</p>
<a href={href('/')} class="mt-6 btn-secondary">{m.error_back_home()}</a>

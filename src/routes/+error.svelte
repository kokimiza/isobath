<script lang="ts">
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';
</script>

<h1 class="text-2xl font-semibold">{m.error_page_title()}</h1>
<p class="mt-2 text-slate-400">{page.status}</p>
<a href={href('/')} class="mt-6 btn-secondary">{m.error_back_home()}</a>

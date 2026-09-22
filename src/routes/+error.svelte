<script lang="ts">
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';
</script>

<h1 class="text-2xl font-semibold">{m.error_page_title()}</h1>
<p class="mt-2 text-muted">{page.status}</p>
{#if page.error?.message}<p class="mt-4 alert" role="alert">{page.error.message}</p>{/if}
<a href={page.url.pathname + page.url.search} data-sveltekit-reload class="mt-6 btn-primary"
	>{m.survey_retry()}</a
>
<a href={href('/')} class="mt-6 btn-secondary">{m.error_back_home()}</a>

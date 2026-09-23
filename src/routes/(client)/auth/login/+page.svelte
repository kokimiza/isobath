<script lang="ts">
	import { page } from '$app/state';
	import { m } from '$lib/paraglide/messages.js';
	import { safeNext } from '$lib/auth.svelte';
	import { href } from '$lib/nav';
	import AuthMethods from '$lib/components/AuthMethods.svelte';
	const next = $derived(safeNext(page.url.searchParams.get('next')) ?? href('/profile'));
</script>

<h1 class="text-2xl font-semibold">{m.login_title()}</h1>
<AuthMethods mode="login" {next} />
<p class="mt-6 text-sm text-muted">
	{m.login_no_account()}
	<a href={href('/auth/signup', { next })} class="text-ocean underline">{m.login_to_signup()}</a>
</p>

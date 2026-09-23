<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import { href } from '$lib/nav';
	import AuthMethods from '$lib/components/AuthMethods.svelte';
	let { data } = $props();
</script>

<h1 class="text-2xl font-semibold">{m.signup_method_title()}</h1>
<p class="mt-2 max-w-md text-body">{m.signup_method_lead()}</p>
<AuthMethods mode="signup" next={data.next} />
<a
	href={href('/auth/signup', { next: data.next })}
	class="mt-6 inline-block text-sm text-ocean underline">{m.signup_review()}</a
>

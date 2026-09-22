<script lang="ts">
	import { m } from '$lib/paraglide/messages.js';
	import SurveyRunner from '$lib/components/SurveyRunner.svelte';
</script>

<SurveyRunner kind="continuous" title={m.survey_continuous_title()} />

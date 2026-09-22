<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '$lib/paraglide/messages.js';
	import { api, type Meta } from '$lib/api.svelte';
	import { auth } from '$lib/auth.svelte';
	import { stageDescription, stageName } from '$lib/i18n';
	import { href } from '$lib/nav';
	import UpdateStatus from '$lib/components/UpdateStatus.svelte';
	import ObservationBasin from '$lib/components/ObservationBasin.svelte';
	import ArrowRight from '@lucide/svelte/icons/arrow-right';

	// Prerendered: live numbers are fetched in the browser only.
	let meta = $state<Meta | null>(null);

	onMount(() => {
		api
			.meta()
			.then((v) => (meta = v))
			.catch(() => (meta = null)); // stats are decorative; the page works without the API
	});
</script>

<section class="landing-intro">
	<div class="intro-copy">
		<h1>{m.landing_headline_1()}<br /><span>{m.landing_headline_2()}</span></h1>
		<p class="intro-statement">{m.landing_intro()}</p>
		<p class="intro-description">{m.landing_explanation()}</p>
		<div class="intro-actions">
			<a href={href(auth.session ? '/profile' : '/survey')} class="btn-primary">
				{auth.session ? m.landing_cta_continue() : m.landing_cta_signup()}<ArrowRight
					size={17}
					strokeWidth={1.5}
					aria-hidden="true"
				/>
			</a>
			<a href={href('/chart')} class="chart-link"
				>{m.profile_links_chart()}<ArrowRight size={16} aria-hidden="true" /></a
			>
		</div>
		<p class="survey-note">{m.landing_survey_note()}</p>
	</div>
	<ObservationBasin />
</section>

<section class="chart-status" aria-label={m.landing_stage_label()}>
	{#if meta}
		<div class="status-title">
			<span class="status-dot" aria-hidden="true"></span><span>{m.landing_stage_label()}</span
			><strong>{stageName[meta.chart.stage]()}</strong>
		</div>
		<div class="status-description">
			<p>{stageDescription[meta.chart.stage]()}</p>
			<p class="mt-2">{m.landing_participants({ count: meta.participants })}</p>
		</div>
		<UpdateStatus updatedAt={meta.updated_at} nextUpdateAt={meta.next_update_at} />
	{:else}
		<p>{m.landing_status_unavailable()}</p>
		<a class="chart-link" href={href('/chart')}
			>{m.nav_chart()}<ArrowRight size={16} aria-hidden="true" /></a
		>
	{/if}
</section>

<section class="observation-story">
	<div class="story-intro">
		<h2>{m.landing_story_title()}</h2>
		<p>{m.landing_story_body()}</p>
	</div>
	<ol class="observation-steps">
		{#each [{ title: m.landing_step_1_title, body: m.landing_step_1_body }, { title: m.landing_step_2_title, body: m.landing_step_2_body }, { title: m.landing_step_3_title, body: m.landing_step_3_body }] as step, i (i)}
			<li>
				<span class="step-number" aria-hidden="true">{i + 1}</span>
				<div>
					<h3>{step.title()}</h3>
					<p>{step.body()}</p>
				</div>
			</li>
		{/each}
	</ol>
</section>

<section class="principle">
	<h2>{m.landing_principle()}</h2>
	<div>
		<p>{m.landing_principle_body()}</p>
		<a class="chart-link" href={href('/legal/research')}
			>{m.landing_research_link()}<ArrowRight size={16} aria-hidden="true" /></a
		>
	</div>
</section>

<style>
	.landing-intro {
		display: grid;
		grid-template-columns: 0.94fr 1.06fr;
		align-items: center;
		gap: 58px;
		padding: 20px 0 50px;
	}
	.intro-copy {
		padding-bottom: 30px;
	}
	h1 {
		font-size: clamp(2rem, 3.5vw, 3.25rem);
		font-weight: 500;
		line-height: 1.7;
		letter-spacing: -0.025em;
	}
	h1 span {
		color: var(--color-ocean);
	}
	.intro-statement {
		margin-top: 30px;
		font-size: 16px;
	}
	.intro-description {
		margin-top: 12px;
		max-width: 29em;
		line-height: 2.1;
		font-size: 14px;
		color: var(--color-body);
	}
	.intro-actions {
		display: flex;
		gap: 26px;
		align-items: center;
		flex-wrap: wrap;
		margin-top: 34px;
	}
	.chart-link {
		display: inline-flex;
		gap: 12px;
		align-items: center;
		font-size: 13px;
		color: var(--color-ocean);
		min-height: 44px;
	}
	.chart-link:hover {
		text-decoration: underline;
	}
	.survey-note {
		font-size: 11px;
		color: var(--color-muted);
		margin-top: 17px;
	}
	.chart-status {
		border-top: 1px solid var(--color-line);
		border-bottom: 1px solid var(--color-line);
		padding: 26px 0;
		display: flex;
		gap: 34px;
		align-items: center;
		justify-content: space-between;
		font-size: 12px;
		color: var(--color-muted);
	}
	.status-title {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 10px;
		flex-shrink: 0;
	}
	.status-title strong {
		font-size: 15px;
		color: var(--color-ink);
		font-weight: 500;
	}
	.status-dot {
		width: 7px;
		height: 7px;
		background: var(--color-ocean);
		border-radius: 50%;
	}
	.status-description {
		max-width: 35em;
	}
	.observation-story {
		display: grid;
		grid-template-columns: 0.9fr 1.1fr;
		gap: 90px;
		padding: 90px 0;
	}
	.story-intro h2,
	.principle h2 {
		font-size: clamp(1.65rem, 2.7vw, 2.2rem);
		font-weight: 500;
	}
	.story-intro p {
		margin-top: 22px;
		color: var(--color-body);
		line-height: 2.1;
		max-width: 24em;
		font-size: 14px;
	}
	.observation-steps {
		display: grid;
		gap: 30px;
	}
	.observation-steps li {
		display: flex;
		align-items: baseline;
		gap: 24px;
	}
	.step-number {
		flex-shrink: 0;
		font-size: 13px;
		color: var(--color-ocean);
		font-variant-numeric: tabular-nums;
	}
	.observation-steps h3 {
		font-size: 18px;
		font-weight: 500;
	}
	.observation-steps p {
		margin-top: 9px;
		font-size: 13px;
		line-height: 2;
		color: var(--color-body);
	}
	.principle {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 60px;
		padding: 42px;
		background: var(--color-mist);
		border-radius: 16px;
		align-items: center;
	}
	.principle h2 {
		font-size: 26px;
	}
	.principle p {
		font-size: 13px;
		line-height: 2;
		color: var(--color-body);
	}
	.principle a {
		margin-top: 12px;
	}
	@media (max-width: 1000px) {
		.landing-intro {
			gap: 32px;
		}
		.intro-actions {
			gap: 10px 22px;
		}
		.chart-status {
			align-items: flex-start;
			flex-wrap: wrap;
			gap: 16px 30px;
		}
		.observation-story {
			gap: 45px;
		}
	}
	@media (max-width: 720px) {
		.landing-intro {
			grid-template-columns: 1fr;
			gap: 24px;
			padding-top: 0;
			padding-bottom: 30px;
		}
		.intro-copy {
			padding-bottom: 0;
		}
		h1 {
			font-size: clamp(2rem, 7.4vw, 3rem);
			line-height: 1.65;
		}
		.intro-statement {
			margin-top: 24px;
			font-size: 14px;
		}
		.intro-description {
			font-size: 13px;
		}
		.intro-actions {
			margin-top: 24px;
		}
		.survey-note {
			font-size: 10px;
		}
		.observation-story {
			grid-template-columns: 1fr;
			gap: 36px;
			padding: 54px 0;
		}
		.story-intro p {
			max-width: none;
		}
		.principle {
			grid-template-columns: 1fr;
			gap: 20px;
			padding: 28px;
		}
		.principle h2 {
			font-size: 23px;
		}
	}
</style>

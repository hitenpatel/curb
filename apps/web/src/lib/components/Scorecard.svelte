<script lang="ts">
	import type { Scorecard } from '../types';

	let { card }: { card: Scorecard } = $props();

	const passPct = $derived(Math.round(card.pass_rate * 100));
</script>

<section class="scorecard" aria-labelledby="scorecard-heading">
	<h2 id="scorecard-heading">Scorecard</h2>
	<dl>
		<div class="stat">
			<dt>Violations</dt>
			<dd>{card.violations_total}</dd>
		</div>
		<div class="stat">
			<dt>Remediations attempted</dt>
			<dd>{card.remediations_attempted}</dd>
		</div>
		<div class="stat">
			<dt>Verified by axe</dt>
			<dd>
				<strong>{card.remediations_verified}</strong>
				<small>/ {card.remediations_attempted || 0}</small>
			</dd>
		</div>
		<div class="stat">
			<dt>Pass rate</dt>
			<dd class="rate" data-rate={passPct}>
				{card.remediations_attempted ? `${passPct}%` : '—'}
			</dd>
		</div>
	</dl>

	{#if Object.keys(card.violations_by_severity).length > 0}
		<div class="breakdown">
			<h3>By severity</h3>
			<ul>
				{#each Object.entries(card.violations_by_severity) as [sev, n] (sev)}
					<li><span class="key">{sev}</span><span class="val">{n}</span></li>
				{/each}
			</ul>
		</div>
	{/if}
</section>

<style>
	.scorecard {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: var(--space-4);
	}
	h2 {
		font-size: 1.125rem;
		margin: 0 0 var(--space-3);
	}
	h3 {
		font-size: 0.875rem;
		margin: var(--space-4) 0 var(--space-2);
		color: var(--color-text-muted);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
		gap: var(--space-3);
		margin: 0;
	}
	.stat {
		display: flex;
		flex-direction: column;
	}
	dt {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	dd {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	dd small {
		font-size: 0.875rem;
		font-weight: 400;
		color: var(--color-text-muted);
	}
	.rate[data-rate='100'] {
		color: #15803d;
	}
	.breakdown ul {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
	}
	.breakdown li {
		display: inline-flex;
		gap: 0.25rem;
		border: 1px solid var(--color-border);
		border-radius: 0.25rem;
		padding: 0.125rem 0.5rem;
		font-size: 0.875rem;
	}
	.breakdown .key {
		color: var(--color-text-muted);
		text-transform: capitalize;
	}
	.breakdown .val {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
</style>

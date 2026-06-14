<script lang="ts">
	import type { Remediation, Violation } from '../types';
	import SeverityBadge from './SeverityBadge.svelte';

	let {
		violation,
		remediation = null
	}: { violation: Violation; remediation?: Remediation | null } = $props();
</script>

<article class="card" aria-labelledby={`v-${violation.id}-title`}>
	<header>
		<SeverityBadge severity={violation.severity} />
		<h3 id={`v-${violation.id}-title`}>
			{violation.rule_id}
			<span class="criterion">WCAG {violation.wcag_criterion}</span>
		</h3>
	</header>

	<p class="description">{violation.help || violation.description}</p>

	<div class="selector">
		<span class="label">Selector</span>
		<code>{violation.selector}</code>
	</div>

	<div class="markup">
		<span class="label">Offending markup</span>
		<pre><code>{violation.markup}</code></pre>
	</div>

	{#if remediation}
		<div class="remediation" data-verified={remediation.verified}>
			<header>
				{#if remediation.verified}
					<span class="badge verified" aria-label="Verified by axe">
						<svg
							width="14"
							height="14"
							viewBox="0 0 16 16"
							aria-hidden="true"
							focusable="false"
						>
							<path
								d="M2 8.5 L6 12 L14 4"
								stroke="currentColor"
								stroke-width="2"
								fill="none"
								stroke-linecap="round"
								stroke-linejoin="round"
							/>
						</svg>
						Verified by axe
					</span>
				{:else}
					<span class="badge unverified" aria-label="Unverified">Proposed (unverified)</span>
				{/if}
				<span class="confidence" title="Agent self-reported confidence">
					confidence {remediation.confidence.toFixed(2)}
				</span>
			</header>
			<p class="explanation">{remediation.explanation}</p>
			<div class="diff" aria-label="Proposed change">
				<div class="row removed">
					<span class="marker" aria-hidden="true">−</span>
					<pre><code>{remediation.patch.original}</code></pre>
				</div>
				<div class="row added">
					<span class="marker" aria-hidden="true">+</span>
					<pre><code>{remediation.patch.fixed}</code></pre>
				</div>
			</div>
			{#if remediation.new_violations.length > 0}
				<p class="regression">
					Rejected — this fix would introduce {remediation.new_violations.length}
					new violation(s): {remediation.new_violations.join(', ')}
				</p>
			{/if}
		</div>
	{/if}

	{#if violation.help_url}
		<a class="help" href={violation.help_url} rel="noreferrer" target="_blank">
			Read the axe rule documentation
			<span class="visually-hidden">(opens in a new tab)</span>
		</a>
	{/if}
</article>

<style>
	.card {
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		padding: var(--space-4);
		background: var(--color-surface);
		display: grid;
		gap: var(--space-3);
		min-width: 0;
		overflow: hidden;
	}
	.card > header {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		flex-wrap: wrap;
	}
	h3 {
		margin: 0;
		font-size: 1.0625rem;
		font-weight: 600;
	}
	.criterion {
		color: var(--color-text-muted);
		font-weight: 500;
		font-size: 0.875rem;
		margin-left: 0.5rem;
	}
	.description {
		margin: 0;
		color: var(--color-text);
	}
	.label {
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		display: block;
		margin-bottom: 0.25rem;
	}
	code {
		font-family: var(--font-mono);
		font-size: 0.875rem;
	}
	.selector code {
		background: rgba(0, 0, 0, 0.04);
		padding: 0.125rem 0.375rem;
		border-radius: 0.25rem;
		word-break: break-all;
	}
	@media (prefers-color-scheme: dark) {
		.selector code {
			background: rgba(255, 255, 255, 0.08);
		}
	}
	.markup pre,
	.diff pre {
		margin: 0;
		overflow-x: auto;
		background: rgba(0, 0, 0, 0.04);
		border-radius: 0.25rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.8125rem;
	}
	@media (prefers-color-scheme: dark) {
		.markup pre,
		.diff pre {
			background: rgba(255, 255, 255, 0.04);
		}
	}
	.remediation {
		border: 1px solid var(--color-border);
		border-left-width: 3px;
		border-left-color: var(--color-accent);
		border-radius: var(--radius);
		padding: var(--space-3);
		background: rgba(109, 40, 217, 0.04);
		display: grid;
		gap: var(--space-2);
	}
	.remediation[data-verified='true'] {
		border-left-color: #15803d;
		background: rgba(21, 128, 61, 0.05);
	}
	.remediation > header {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		flex-wrap: wrap;
	}
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.125rem 0.5rem;
		border-radius: 0.25rem;
		border: 1px solid currentColor;
	}
	.badge.verified {
		color: #15803d;
		background: rgba(21, 128, 61, 0.12);
	}
	.badge.unverified {
		color: var(--color-text-muted);
	}
	.confidence {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}
	.explanation {
		margin: 0;
		font-size: 0.9375rem;
		line-height: 1.5;
	}
	.diff {
		display: grid;
		gap: 0.25rem;
	}
	.diff .row {
		display: grid;
		grid-template-columns: 1.25rem 1fr;
		gap: 0.25rem;
		align-items: start;
	}
	.diff .removed pre {
		background: rgba(220, 38, 38, 0.08);
	}
	.diff .added pre {
		background: rgba(21, 128, 61, 0.08);
	}
	.diff .marker {
		font-family: var(--font-mono);
		font-weight: 700;
		padding-top: 0.5rem;
	}
	.diff .removed .marker {
		color: #b91c1c;
	}
	.diff .added .marker {
		color: #15803d;
	}
	.regression {
		margin: 0;
		font-size: 0.875rem;
		color: #b91c1c;
	}
	.help {
		font-size: 0.875rem;
		color: var(--color-accent);
	}
	.visually-hidden {
		position: absolute;
		clip: rect(0 0 0 0);
		width: 1px;
		height: 1px;
		overflow: hidden;
		white-space: nowrap;
	}
</style>

<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchAudit } from '$lib/api';
	import LiveAnnouncer from '$lib/components/LiveAnnouncer.svelte';
	import ScorecardComponent from '$lib/components/Scorecard.svelte';
	import ViolationCard from '$lib/components/ViolationCard.svelte';
	import type { AuditDetail, AuditState, Remediation } from '$lib/types';

	let { data }: { data: { detail: AuditDetail } } = $props();

	// Snapshot the SSR-resolved detail into mutable state; SSE updates will
	// flow into it. svelte-ignore: yes, we mean to read data.detail once.
	// eslint-disable-next-line svelte/no-reactive-reassign
	// svelte-ignore state_referenced_locally
	let detail = $state<AuditDetail>(data.detail);
	// svelte-ignore state_referenced_locally
	let live = $state<string>(`Audit ${data.detail.audit.status}.`);

	function applyRemediation(audit: AuditDetail, r: Remediation): AuditDetail {
		// Replace if a remediation for the same violation already exists; otherwise append.
		const idx = audit.remediations.findIndex((e) => e.violation_id === r.violation_id);
		const next = audit.remediations.slice();
		if (idx >= 0) next[idx] = r;
		else next.push(r);
		return { ...audit, remediations: next };
	}

	// Re-fetch the full detail (cheap GET) to refresh the scorecard etc.
	async function refresh() {
		try {
			detail = await fetchAudit(detail.audit.id);
		} catch {
			// SSE has the up-to-date data; a refresh miss isn't fatal.
		}
	}

	onMount(() => {
		if (detail.audit.status === 'complete' || detail.audit.status === 'failed') {
			return;
		}

		const source = new EventSource(`/api/audits/${detail.audit.id}/events`);

		source.addEventListener('status', (ev) => {
			const payload = JSON.parse((ev as MessageEvent).data).payload as { status: AuditState };
			detail = { ...detail, audit: { ...detail.audit, status: payload.status } };
			live = `Audit ${payload.status}.`;
		});

		source.addEventListener('violation', () => {
			// We don't append per-event here; the DB-backed refresh below brings
			// the violation row, scorecard, and guidance in one consistent shape.
			live = `Found violation.`;
			void refresh();
		});

		source.addEventListener('remediation', (ev) => {
			const payload = JSON.parse((ev as MessageEvent).data).payload as Remediation & {
				model: string;
			};
			detail = applyRemediation(detail, payload);
			live = payload.verified
				? `Verified fix for ${payload.wcag_criterion}.`
				: `Proposed fix for ${payload.wcag_criterion}.`;
		});

		source.addEventListener('complete', () => {
			live = `Audit complete.`;
			void refresh();
			source.close();
		});

		source.addEventListener('error', () => {
			// SSE 'error' is emitted both on transport drop and on the server's
			// 'error' kind. Try to recover by re-fetching; SSE will reopen
			// automatically unless we close.
			void refresh();
		});

		return () => source.close();
	});

	const remediationByViolation = $derived(
		new Map(detail.remediations.map((r) => [r.violation_id, r]))
	);

	// Group violations by WCAG criterion for the report layout.
	const groups = $derived.by(() => {
		const map = new Map<string, typeof detail.violations>();
		for (const v of detail.violations) {
			const list = map.get(v.wcag_criterion) ?? [];
			list.push(v);
			map.set(v.wcag_criterion, list);
		}
		return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
	});

	const isRunning = $derived(
		detail.audit.status === 'queued' || detail.audit.status === 'running'
	);
</script>

<svelte:head>
	<title>Curb &mdash; audit of {detail.audit.url}</title>
</svelte:head>

<LiveAnnouncer message={live} />

<section class="report">
	<header class="report-header">
		<p class="back"><a href="/">← Run another audit</a></p>
		<h1>Audit of <code>{detail.audit.url}</code></h1>
		<p class="status" data-status={detail.audit.status}>
			Status: <strong>{detail.audit.status}</strong>
			{#if isRunning}
				<span class="spinner" aria-hidden="true"></span>
			{/if}
		</p>
		{#if detail.audit.error}
			<p class="error" role="alert">{detail.audit.error}</p>
		{/if}
	</header>

	<ScorecardComponent card={detail.scorecard} />

	{#if detail.violations.length === 0 && detail.audit.status === 'complete'}
		<p class="empty">axe didn&rsquo;t flag any WCAG A/AA violations on this page.</p>
	{/if}

	{#each groups as [criterion, vs] (criterion)}
		<section class="group" aria-labelledby={`criterion-${criterion}`}>
			<h2 id={`criterion-${criterion}`}>WCAG {criterion}</h2>
			<div class="cards">
				{#each vs as violation (violation.id)}
					<ViolationCard
						{violation}
						remediation={remediationByViolation.get(violation.id) ?? null}
					/>
				{/each}
			</div>
		</section>
	{/each}
</section>

<style>
	.report {
		display: grid;
		gap: var(--space-6);
	}

	.report-header h1 {
		font-size: 1.5rem;
		margin: var(--space-2) 0 var(--space-2);
		overflow-wrap: anywhere;
		min-width: 0;
	}

	.report-header h1 code {
		font-family: var(--font-mono);
		font-size: 1.125rem;
		overflow-wrap: anywhere;
	}

	.back a {
		color: var(--color-text-muted);
		font-size: 0.875rem;
		text-decoration: none;
	}
	.back a:hover {
		text-decoration: underline;
	}

	.status {
		margin: 0;
		color: var(--color-text-muted);
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}

	.status[data-status='complete'] strong {
		color: #15803d;
	}
	.status[data-status='failed'] strong {
		color: #b91c1c;
	}
	.status[data-status='running'] strong,
	.status[data-status='queued'] strong {
		color: var(--color-accent);
	}

	.spinner {
		width: 0.75rem;
		height: 0.75rem;
		border: 2px solid var(--color-text-muted);
		border-top-color: var(--color-accent);
		border-radius: 50%;
		display: inline-block;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.spinner {
			animation: none;
		}
	}

	.error {
		color: #b91c1c;
	}

	.empty {
		color: var(--color-text-muted);
		text-align: center;
		padding: var(--space-6);
		border: 1px dashed var(--color-border);
		border-radius: var(--radius);
	}

	.group h2 {
		font-size: 1.125rem;
		margin: 0 0 var(--space-3);
	}

	.cards {
		display: grid;
		gap: var(--space-3);
	}
</style>

<script lang="ts">
	const apiBase = import.meta.env.PUBLIC_API_URL ?? '';

	let status = $state<'idle' | 'loading' | 'ok' | 'error'>('idle');
	let message = $state<string>('');

	async function ping() {
		status = 'loading';
		try {
			const response = await fetch(`${apiBase}/api/hello`);
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const body = await response.json();
			message = body.message;
			status = 'ok';
		} catch (error) {
			message = error instanceof Error ? error.message : 'Unknown error';
			status = 'error';
		}
	}
</script>

<svelte:head>
	<title>Curb — verified WCAG fixes</title>
</svelte:head>

<section>
	<h1>An accessibility auditor with a self-check loop.</h1>
	<p class="lede">
		Curb detects WCAG 2.2 issues deterministically with axe-core, proposes a code-level fix,
		and re-runs axe against the patched DOM before showing it to you. The eval harness gates
		every deploy on a deterministic re-run-axe pass rate.
	</p>
	<p>Phase 0: the live shell. Detection lands in Phase 1.</p>

	<button type="button" onclick={ping} disabled={status === 'loading'}>
		{status === 'loading' ? 'Pinging…' : 'Ping the API'}
	</button>

	<output aria-live="polite">
		{#if status === 'ok'}
			<span class="ok">API says: {message}</span>
		{:else if status === 'error'}
			<span class="error">Could not reach the API: {message}</span>
		{/if}
	</output>
</section>

<style>
	h1 {
		font-size: clamp(1.75rem, 2.5vw + 1rem, 2.75rem);
		line-height: 1.15;
		margin: 0 0 var(--space-4) 0;
	}

	.lede {
		font-size: 1.125rem;
		color: var(--color-text-muted);
		max-width: 40rem;
	}

	button {
		appearance: none;
		font: inherit;
		font-weight: 600;
		padding: var(--space-3) var(--space-6);
		background: var(--color-accent);
		color: var(--color-accent-contrast);
		border: 1px solid transparent;
		border-radius: var(--radius);
		cursor: pointer;
		margin-top: var(--space-4);
	}

	button:disabled {
		opacity: 0.6;
		cursor: progress;
	}

	output {
		display: block;
		margin-top: var(--space-4);
		min-height: 1.5em;
	}

	.ok {
		color: var(--color-text);
	}

	.error {
		color: #b91c1c;
	}
</style>

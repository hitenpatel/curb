<script lang="ts">
	import { goto } from '$app/navigation';
	import { startAudit } from '$lib/api';

	const SAMPLE_AUDITS: { url: string; label: string; note: string }[] = [
		{
			url: 'https://dequeuniversity.com/demo/mars/',
			label: 'Deque Mars demo',
			note: 'Intentionally broken — known to surface 40+ violations across 8 rule types.'
		},
		{
			url: 'https://example.com/',
			label: 'example.com',
			note: 'Clean baseline — should return zero violations.'
		}
	];

	let url = $state('');
	let useBYOK = $state(false);
	let byokProvider = $state('google-gla');
	let byokKey = $state('');
	let submitting = $state(false);
	let error = $state<string | null>(null);

	async function audit(event: SubmitEvent) {
		event.preventDefault();
		if (!url.trim()) return;
		submitting = true;
		error = null;
		try {
			const { id } = await startAudit({
				url: url.trim(),
				model_provider: useBYOK ? byokProvider : undefined,
				model_api_key: useBYOK ? byokKey.trim() : undefined
			});
			await goto(`/audit/${id}`);
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
			submitting = false;
		}
	}
</script>

<svelte:head>
	<title>Curb — verified WCAG fixes</title>
	<meta
		name="description"
		content="An AI accessibility auditor that proposes verified code-level fixes for WCAG violations, scored by an eval harness."
	/>
</svelte:head>

<section class="hero">
	<h1>An accessibility auditor with a self-check loop.</h1>
	<p class="lede">
		Curb detects WCAG 2.2 issues deterministically with axe-core, proposes a code-level fix, and
		re-runs axe against the patched DOM before showing it to you. Every &ldquo;verified&rdquo;
		remediation has been confirmed by axe, not just by the model.
	</p>

	<form onsubmit={audit} aria-labelledby="audit-form-heading">
		<h2 id="audit-form-heading" class="visually-hidden">Run an audit</h2>
		<div class="field">
			<label for="url">URL to audit</label>
			<input
				id="url"
				name="url"
				type="url"
				inputmode="url"
				placeholder="https://example.com"
				bind:value={url}
				required
				autocomplete="off"
				autocapitalize="off"
				spellcheck="false"
			/>
		</div>

		<details class="byok" bind:open={useBYOK}>
			<summary>Use my own model key (BYOK)</summary>
			<p class="hint">
				Your key is sent on the audit request and forgotten as soon as the run completes &mdash;
				never persisted server-side, never logged.
			</p>
			<div class="byok-grid">
				<div class="field">
					<label for="provider">Provider</label>
					<select id="provider" bind:value={byokProvider}>
						<option value="google-gla">Google AI Studio (Gemini)</option>
						<option value="groq">Groq</option>
						<option value="openai">OpenAI</option>
					</select>
				</div>
				<div class="field">
					<label for="key">API key</label>
					<input
						id="key"
						type="password"
						bind:value={byokKey}
						autocomplete="off"
						spellcheck="false"
					/>
				</div>
			</div>
		</details>

		<button type="submit" disabled={submitting || !url}>
			{submitting ? 'Starting…' : 'Audit this URL'}
		</button>

		{#if error}
			<p class="error" role="alert">Could not start the audit: {error}</p>
		{/if}
	</form>
</section>

<section class="samples" aria-labelledby="samples-heading">
	<h2 id="samples-heading">Sample audits</h2>
	<p class="hint">Skip the URL input &mdash; these demo a real run end-to-end.</p>
	<ul>
		{#each SAMPLE_AUDITS as sample (sample.url)}
			<li>
				<button
					type="button"
					class="sample"
					onclick={async () => {
						url = sample.url;
						await audit(new SubmitEvent('submit'));
					}}
				>
					<span class="sample-label">{sample.label}</span>
					<span class="sample-url">{sample.url}</span>
					<span class="sample-note">{sample.note}</span>
				</button>
			</li>
		{/each}
	</ul>
</section>

<style>
	.hero h1 {
		font-size: clamp(1.75rem, 2.5vw + 1rem, 2.75rem);
		line-height: 1.15;
		margin: 0 0 var(--space-4);
	}
	.lede {
		font-size: 1.125rem;
		color: var(--color-text-muted);
		max-width: 42rem;
		margin-bottom: var(--space-6);
	}

	form {
		display: grid;
		gap: var(--space-4);
		max-width: 42rem;
	}

	.field {
		display: grid;
		gap: var(--space-2);
	}

	label {
		font-weight: 600;
		font-size: 0.9375rem;
	}

	input,
	select {
		font: inherit;
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-text);
	}

	input:focus,
	select:focus,
	summary:focus,
	button:focus {
		/* :focus-visible from app.css handles the outline; this keeps consistency. */
		outline: 3px solid var(--color-focus);
		outline-offset: 2px;
	}

	.byok > summary {
		font-weight: 600;
		font-size: 0.9375rem;
		cursor: pointer;
		padding: var(--space-2) 0;
	}

	.byok-grid {
		display: grid;
		grid-template-columns: minmax(10rem, 1fr) minmax(15rem, 2fr);
		gap: var(--space-4);
	}

	.hint {
		color: var(--color-text-muted);
		font-size: 0.875rem;
		margin: 0 0 var(--space-2);
	}

	button[type='submit'] {
		appearance: none;
		font: inherit;
		font-weight: 600;
		padding: var(--space-3) var(--space-6);
		background: var(--color-accent);
		color: var(--color-accent-contrast);
		border: 1px solid transparent;
		border-radius: var(--radius);
		cursor: pointer;
		justify-self: start;
	}

	button[type='submit']:disabled {
		opacity: 0.6;
		cursor: progress;
	}

	.error {
		color: #b91c1c;
	}

	.samples {
		margin-top: var(--space-12);
		border-top: 1px solid var(--color-border);
		padding-top: var(--space-6);
	}

	.samples h2 {
		font-size: 1.25rem;
		margin: 0 0 var(--space-2);
	}

	.samples ul {
		list-style: none;
		padding: 0;
		margin: var(--space-4) 0 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
		gap: var(--space-3);
	}

	.sample {
		display: grid;
		gap: 0.25rem;
		width: 100%;
		text-align: left;
		padding: var(--space-3) var(--space-4);
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		cursor: pointer;
		font: inherit;
	}

	.sample:hover {
		border-color: var(--color-accent);
	}

	.sample-label {
		font-weight: 600;
	}

	.sample-url {
		font-family: var(--font-mono);
		font-size: 0.8125rem;
		color: var(--color-text-muted);
		word-break: break-all;
	}

	.sample-note {
		font-size: 0.875rem;
		color: var(--color-text-muted);
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

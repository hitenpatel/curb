<svelte:head>
	<title>Methodology — Curb</title>
	<meta
		name="description"
		content="How Curb audits pages, what a 'verified' fix does and does not mean, and why automated checks can never replace human accessibility review."
	/>
	<link rel="canonical" href="https://a11y.hiten.dev/methodology" />
</svelte:head>

<article class="methodology">
	<h1>Methodology</h1>
	<p class="lede">
		Curb is built on one rule: the model never grades its own homework. Everything below is the
		exact pipeline &mdash; including what it can&rsquo;t do.
	</p>

	<h2>The pipeline</h2>
	<ol>
		<li>
			<strong>Deterministic detection.</strong> A headless Chromium loads the page and runs
			<a href="https://github.com/dequelabs/axe-core" rel="noreferrer">axe-core</a>. Every
			violation Curb reports comes from axe &mdash; the LLM is never asked to
			&ldquo;find&rdquo; issues, because models hallucinate issues and miss real ones.
		</li>
		<li>
			<strong>Grounded remediation.</strong> For each violation, the agent retrieves matching
			WCAG&nbsp;2.2 and ARIA Authoring Practices guidance from a pgvector store and proposes a
			code-level patch with an explanation and a self-reported confidence score.
		</li>
		<li>
			<strong>Mechanical verification.</strong> The worker applies the patch to a copy of the
			DOM and re-runs axe. A fix is marked <em>verified</em> only if the original violation is
			gone <em>and</em> the patch introduced no new violations. Fixes that fail either check are
			shown as <em>proposed (unverified)</em> or rejected outright.
		</li>
	</ol>

	<h2>What &ldquo;verified&rdquo; means</h2>
	<p>
		Verified means one thing: <strong>an axe re-scan of the patched DOM no longer reports the
		violation, and no new violations appeared.</strong> It is a mechanical regression check, not
		an accessibility sign-off.
	</p>

	<h2>What &ldquo;verified&rdquo; does <em>not</em> mean</h2>
	<ul>
		<li>
			<strong>It is not WCAG conformance.</strong> Automated tools detect roughly a third to a
			half of WCAG failures. A page with zero axe violations can still be unusable with a screen
			reader.
		</li>
		<li>
			<strong>It is not human judgement.</strong> axe can confirm an <code>alt</code> attribute
			exists; it cannot confirm the text is meaningful. Curb flags these cases on each fix with
			a &ldquo;needs a human&rdquo; note rather than pretending the check is complete.
		</li>
		<li>
			<strong>It is not a substitute for assistive-technology testing.</strong> Real review
			means keyboard-only passes and screen readers (NVDA, VoiceOver) driven by people who use
			them.
		</li>
	</ul>

	<h2>Honest demo mechanics</h2>
	<ul>
		<li>
			The sample audits on the home page are precomputed real runs &mdash; same pipeline, stored
			results &mdash; so the demo doesn&rsquo;t cost a Chromium + LLM run per click.
		</li>
		<li>
			Anonymous live audits are rate-limited per IP. Bringing your own model key raises the
			limit because the inference cost becomes yours.
		</li>
		<li>
			BYOK keys travel on the job queue only: never persisted, never logged, forgotten when the
			run completes.
		</li>
	</ul>

	<p class="closing">
		Full architecture, eval harness, and source:
		<a href="https://github.com/hitenpatel/curb" rel="noreferrer">github.com/hitenpatel/curb</a>.
	</p>
</article>

<style>
	.methodology {
		max-width: 42rem;
	}
	h1 {
		font-size: clamp(1.6rem, 2vw + 1rem, 2.25rem);
		margin: 0 0 var(--space-4);
	}
	.lede {
		font-size: 1.125rem;
		color: var(--color-text-muted);
		margin-bottom: var(--space-6);
	}
	h2 {
		font-size: 1.25rem;
		margin: var(--space-8) 0 var(--space-3);
	}
	ol,
	ul {
		display: grid;
		gap: var(--space-3);
		padding-left: 1.25rem;
		margin: 0;
	}
	li {
		line-height: 1.6;
	}
	code {
		font-family: var(--font-mono);
		font-size: 0.875em;
	}
	a {
		color: var(--color-accent);
	}
	.closing {
		margin-top: var(--space-8);
		border-top: 1px solid var(--color-border);
		padding-top: var(--space-4);
		color: var(--color-text-muted);
	}
</style>

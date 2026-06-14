<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<a class="skip-link" href="#main">Skip to main content</a>
<header>
	<nav aria-label="Primary">
		<a class="brand" href="/">Curb</a>
		<span class="tagline">verified WCAG fixes</span>
	</nav>
</header>
<main id="main" tabindex="-1">
	{@render children()}
</main>
<footer>
	<small>
		Curb &mdash; an AI accessibility auditor with a verified-by-axe self-check loop.
		<a href="https://github.com/hitenpatel/curb" rel="noreferrer">Source on GitHub</a>.
	</small>
</footer>

<style>
	.skip-link {
		position: absolute;
		left: -9999px;
		top: 0;
		background: var(--color-accent);
		color: var(--color-accent-contrast);
		padding: var(--space-2) var(--space-4);
		text-decoration: none;
		border-radius: 0 0 var(--radius) 0;
		z-index: 100;
	}

	.skip-link:focus {
		left: 0;
	}

	header {
		border-bottom: 1px solid var(--color-border);
		background: var(--color-surface);
	}

	nav {
		display: flex;
		align-items: baseline;
		gap: var(--space-4);
		max-width: 64rem;
		margin: 0 auto;
		padding: var(--space-4) var(--space-6);
	}

	.brand {
		font-weight: 700;
		font-size: 1.25rem;
		color: var(--color-text);
		text-decoration: none;
	}

	.tagline {
		color: var(--color-text-muted);
		font-size: 0.9rem;
	}

	main {
		max-width: 64rem;
		margin: 0 auto;
		padding: var(--space-8) var(--space-6);
	}

	footer {
		max-width: 64rem;
		margin: 0 auto;
		padding: var(--space-6);
		color: var(--color-text-muted);
		border-top: 1px solid var(--color-border);
		margin-top: var(--space-12);
	}
</style>

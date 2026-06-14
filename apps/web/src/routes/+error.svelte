<script lang="ts">
	import { page } from '$app/stores';
</script>

<svelte:head>
	<title>{$page.status} &mdash; Curb</title>
</svelte:head>

<section>
	<h1>{$page.status} &mdash; {$page.error?.message ?? 'Something went wrong'}</h1>
	<p>
		<a href="/">Go back to the start</a>
	</p>
</section>

<style>
	h1 {
		font-size: 1.5rem;
	}
	a {
		color: var(--color-accent);
	}
</style>

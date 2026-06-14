<!-- A polite aria-live region for announcing status changes to assistive tech
without moving focus. The region exists in the DOM from page load; AT
ignores changes when it isn't there yet. -->
<script lang="ts">
	let { message }: { message: string } = $props();
</script>

<output class="sr-only" aria-live="polite">{message}</output>

<style>
	.sr-only {
		position: absolute;
		clip: rect(0 0 0 0);
		width: 1px;
		height: 1px;
		overflow: hidden;
		white-space: nowrap;
	}
</style>

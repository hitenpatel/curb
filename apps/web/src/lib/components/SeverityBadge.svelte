<script lang="ts">
	import type { Severity } from '../types';

	let { severity }: { severity: Severity } = $props();
</script>

<span class="badge {severity}" data-severity={severity}>{severity}</span>

<style>
	.badge {
		display: inline-block;
		padding: 0.125rem 0.5rem;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		border-radius: 0.25rem;
		border: 1px solid currentColor;
		color: var(--color-text);
		background: var(--color-surface);
	}
	.critical {
		color: #991b1b;
		background: #fee2e2;
		border-color: #fca5a5;
	}
	.serious {
		color: #92400e;
		background: #fef3c7;
		border-color: #fcd34d;
	}
	.moderate {
		color: #1e40af;
		background: #dbeafe;
		border-color: #93c5fd;
	}
	.minor {
		color: #374151;
		background: #f3f4f6;
		border-color: #d1d5db;
	}
	@media (prefers-color-scheme: dark) {
		.critical {
			color: #fecaca;
			background: #7f1d1d;
			border-color: #b91c1c;
		}
		.serious {
			color: #fde68a;
			background: #78350f;
			border-color: #b45309;
		}
		.moderate {
			color: #bfdbfe;
			background: #1e3a8a;
			border-color: #1d4ed8;
		}
		.minor {
			color: #e5e7eb;
			background: #1f2937;
			border-color: #4b5563;
		}
	}
</style>

// Tiny API client. Web + API are on the same Host (Traefik routes /api/* to
// FastAPI), so relative paths work in prod. In SSR we go through fetch which
// SvelteKit hands us; on the client, the browser's native fetch is used.

import type { AuditDetail } from './types';

export interface StartAuditOptions {
	url: string;
	model_provider?: string;
	model_api_key?: string;
}

export async function startAudit(
	opts: StartAuditOptions,
	fetcher: typeof fetch = fetch
): Promise<{ id: string }> {
	const response = await fetcher('/api/audits', {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({
			url: opts.url,
			model_provider: opts.model_provider || null,
			model_api_key: opts.model_api_key || null
		})
	});
	if (!response.ok) {
		const body = await response.text().catch(() => '');
		throw new Error(`POST /api/audits failed (${response.status}): ${body}`);
	}
	return response.json();
}

export async function fetchAudit(
	auditId: string,
	fetcher: typeof fetch = fetch
): Promise<AuditDetail> {
	const response = await fetcher(`/api/audits/${auditId}`);
	if (!response.ok) {
		throw new Error(`GET /api/audits/${auditId} failed: ${response.status}`);
	}
	return response.json();
}

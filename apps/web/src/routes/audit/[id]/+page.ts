import { error } from '@sveltejs/kit';
import { fetchAudit } from '$lib/api';
import type { PageLoad } from './$types';

// Universal load: runs on the server for the initial request (so the page
// is meaningful without JS) and on the client for client-side navigation.
// The SSE stream takes over after mount.
export const load: PageLoad = async ({ params, fetch }) => {
	try {
		const detail = await fetchAudit(params.id, fetch);
		return { detail };
	} catch (e) {
		throw error(404, e instanceof Error ? e.message : 'Audit not found');
	}
};

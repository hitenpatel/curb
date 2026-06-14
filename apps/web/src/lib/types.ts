// Mirrors the Pydantic models in packages/shared/curb_shared/models.py.
// Hand-written rather than generated so the contract change is visible in
// review; keep in lockstep with the Python side when the schema evolves.

export type Severity = 'critical' | 'serious' | 'moderate' | 'minor';

export type AuditState = 'queued' | 'running' | 'complete' | 'failed';

export interface Audit {
	id: string;
	url: string;
	status: AuditState;
	created_at: string;
	updated_at: string;
	error: string | null;
	violation_count: number;
}

export interface Violation {
	id: string;
	audit_id: string;
	rule_id: string;
	wcag_criterion: string;
	description: string;
	help: string;
	help_url: string;
	severity: Severity;
	selector: string;
	markup: string;
	failure_summary: string;
}

export interface Patch {
	target_selector: string;
	original: string;
	fixed: string;
	unified_diff: string;
}

export interface Remediation {
	violation_id: string;
	wcag_criterion: string;
	severity: Severity;
	explanation: string;
	patch: Patch;
	confidence: number;
	verified: boolean;
	new_violations: string[];
}

export interface Scorecard {
	violations_total: number;
	violations_by_severity: Record<string, number>;
	violations_by_criterion: Record<string, number>;
	remediations_attempted: number;
	remediations_verified: number;
	pass_rate: number;
	regressions_avoided: number;
}

export interface AuditDetail {
	audit: Audit;
	violations: Violation[];
	remediations: Remediation[];
	scorecard: Scorecard;
}

export interface GuidanceHit {
	criterion: string;
	title: string;
	score: number;
}

// SSE event payload shapes — `kind` keyed.
export type AuditEvent =
	| { kind: 'status'; payload: { status: AuditState } }
	| {
			kind: 'violation';
			payload: {
				rule_id: string;
				wcag_criterion: string;
				severity: Severity;
				selector: string;
				guidance: GuidanceHit[];
			};
	  }
	| {
			kind: 'remediation';
			payload: {
				violation_id: string;
				wcag_criterion: string;
				verified: boolean;
				confidence: number;
				explanation: string;
				patch: Patch;
				new_violations: string[];
				model: string;
			};
	  }
	| { kind: 'complete'; payload: { violation_count: number } }
	| { kind: 'error'; payload: { error: string } };

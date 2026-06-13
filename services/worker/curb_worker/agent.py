"""Remediation agent.

A Pydantic AI Agent that proposes a code-level fix for one violation. It
has access to one tool, `validate`, which applies the proposed patch to
the live page and re-runs axe-core scoped to the parent of the original
node. The agent is instructed: never return verified=true until validate
confirms.

The worker doesn't trust the agent's claim alone. After the run we override
the Remediation's verified flag to the result of the *last* validate call
seen on this audit. If validate was never called, verified is forced false.
This is the defence-in-depth that makes the contract honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

import structlog
from curb_shared import Patch, Remediation, ValidationResult, Violation
from pydantic_ai import Agent, RunContext

from curb_worker.retrieval import Guidance
from curb_worker.validate import apply_patch_and_check, baseline_for

if TYPE_CHECKING:
    from playwright.async_api import Page

log = structlog.get_logger()


@dataclass
class AgentDeps:
    """What the agent's tools need from the surrounding pipeline."""

    page: Page
    violation: Violation
    baseline_rule_ids: frozenset[str]
    last_validation: ValidationResult | None = field(default=None)
    validate_calls: int = field(default=0)


SYSTEM_PROMPT = """\
You are a WCAG 2.2 accessibility remediation expert.

You are given ONE accessibility violation flagged by axe-core. Your job is
to propose a MINIMAL, code-level fix for that one violation, grounded in
the supplied WCAG / ARIA guidance, then USE the `validate` tool to verify
the fix actually resolves it without introducing new violations.

Hard rules:
1. Output a Remediation. Set verified=true ONLY after the validate tool
   has returned resolved=true with an empty new_violations list. If you
   set verified=true without that confirmation, the worker will override
   it to false and your remediation will be rejected.
2. The `patch.fixed` field must be a single replacement element's outerHTML
   that resolves the violation. Keep the same element type and attributes
   except where the fix requires changes. Do not invent new ids or classes.
3. Cite the WCAG criterion in your explanation. Reference the guidance
   passages that informed the change.
4. You may call validate at most twice. If the first attempt fails, revise
   once based on the returned notes; do not loop further.
5. Confidence is a number in [0, 1]. Use it honestly — 0.95+ only for
   straightforward fixes (missing alt, missing aria-label); 0.5-0.7 for
   contrast/structural fixes where the chosen value is a judgement call.

unified_diff in the patch can be a unified-diff hunk between original
and fixed; if unsure, a single-line summary is fine.
"""


def build_agent(model: object) -> Agent[AgentDeps, Remediation]:
    """Construct an Agent typed to our deps + output. `model` is anything
    Pydantic AI accepts: a Model instance, a string, or a TestModel for tests.
    """
    # pydantic-ai's Agent typing is a Literal-soup over known model strings;
    # our gateway returns dynamic Model instances + we pass TestModel from
    # tests. Cast through Any so mypy stops trying to match an overload.
    agent: Agent[AgentDeps, Remediation] = cast(
        Any,
        Agent(
            model=cast(Any, model),
            deps_type=AgentDeps,
            output_type=Remediation,
            system_prompt=SYSTEM_PROMPT,
        ),
    )

    @agent.tool
    async def validate(ctx: RunContext[AgentDeps], patch: Patch) -> ValidationResult:
        """Apply the proposed patch to the live page and re-run axe-core
        scoped to the surrounding region. Returns whether the original
        violation is resolved and whether any new violations were introduced.
        """
        ctx.deps.validate_calls += 1
        result = await apply_patch_and_check(
            ctx.deps.page,
            target_selector=patch.target_selector,
            fixed_markup=patch.fixed,
            original_rule_id=ctx.deps.violation.rule_id,
            baseline_rule_ids=ctx.deps.baseline_rule_ids,
        )
        ctx.deps.last_validation = result
        log.info(
            "validate_call",
            violation_id=str(ctx.deps.violation.id),
            resolved=result.resolved,
            new_violations=result.new_violations,
        )
        return result

    return agent


def _build_prompt(violation: Violation, guidance: list[Guidance]) -> str:
    """Compose the user-side prompt for one remediation run."""
    guidance_blob = (
        "\n\n".join(f"--- {g.title} (score={g.score:.2f}) ---\n{g.body}" for g in guidance)
        or "(no guidance retrieved)"
    )
    return f"""\
Violation to fix
================
rule_id:        {violation.rule_id}
WCAG criterion: {violation.wcag_criterion}
severity:       {violation.severity}
description:    {violation.description}
help:           {violation.help}
help_url:       {violation.help_url}

Offending element (CSS selector): {violation.selector}

Offending markup:
```html
{violation.markup}
```

axe failure summary: {violation.failure_summary or "(none)"}

Retrieved WCAG / ARIA guidance
==============================
{guidance_blob}

Propose a minimal fix, then call `validate` with your proposed patch.
Only set verified=true after validate confirms.
"""


async def propose_and_verify(
    *,
    agent: Agent[AgentDeps, Remediation],
    page: Page,
    violation: Violation,
    guidance: list[Guidance],
    model_label: str,
) -> Remediation | None:
    """Run the agent end-to-end for one violation; enforce verified-only.

    Returns the Remediation (with verified honestly set by us, not by the
    agent's claim) or None if the agent raised. None is logged loudly so
    a model-side outage doesn't silently degrade the audit."""
    _, baseline = await baseline_for(page, violation)
    deps = AgentDeps(page=page, violation=violation, baseline_rule_ids=baseline)
    try:
        result = await agent.run(_build_prompt(violation, guidance), deps=deps)
    except Exception as exc:
        # Short error only — `log.exception` was dumping multi-KB tracebacks
        # for every Gemini 429 and tripping BlockingIOError on stdout. The
        # type + truncated message is enough to triage; full traceback is
        # captured by the harness when it cares.
        log.warning(
            "agent_run_failed",
            violation_id=str(violation.id),
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        return None

    remediation = result.output
    # Defence in depth: only the worker decides 'verified', not the agent.
    confirmed = (
        deps.last_validation is not None
        and deps.last_validation.resolved
        and not deps.last_validation.new_violations
    )
    remediation = remediation.model_copy(
        update={
            "verified": confirmed,
            "new_violations": (deps.last_validation.new_violations if deps.last_validation else []),
            "violation_id": violation.id,
            "wcag_criterion": violation.wcag_criterion,
            "severity": violation.severity,
        }
    )
    log.info(
        "remediation_proposed",
        violation_id=str(violation.id),
        verified=remediation.verified,
        validate_calls=deps.validate_calls,
        model=model_label,
    )
    return remediation

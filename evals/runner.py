"""End-to-end eval runner: golden case → agent → scorer.

For one golden case (a planted-bad HTML fixture + an expected axe rule
to fix), the runner:

1. Loads the fixture into a fresh Playwright page.
2. Runs detection (axe-core) — asserts the expected rule_id is flagged.
3. Picks the violation whose rule_id matches the case's expected_rule_id.
4. Retrieves WCAG guidance (skipped when CURB_TEST_DATABASE_URL is unset).
5. Runs the remediation agent against the live page.
6. Returns the EvalResult: primary metric = `verified` (resolved by axe
   with no regressions), secondary metric placeholders for the LLM-judge
   that lands as a follow-up.

No DB required for the primary metric — the worker repository is bypassed
entirely. The scorer talks directly to the agent + validate plumbing.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
from curb_shared import Remediation
from curb_worker.agent import build_agent, propose_and_verify
from curb_worker.detector import run_axe_on_page
from curb_worker.gateway import build_model, resolve
from curb_worker.retrieval import Guidance, retrieve_for_violation
from playwright.async_api import async_playwright


@dataclass
class GoldenCase:
    """One eval case. Loaded from evals/golden/*.json."""

    id: str
    title: str
    wcag_criterion: str
    expected_rule_id: str
    fixture_html: str

    @classmethod
    def from_path(cls, path: Path) -> GoldenCase:
        data: dict[str, Any] = json.loads(path.read_text())
        return cls(
            id=data["id"],
            title=data["title"],
            wcag_criterion=data["wcag_criterion"],
            expected_rule_id=data["expected_rule_id"],
            fixture_html=data["fixture_html"],
        )


@dataclass
class EvalResult:
    """Per-case outcome. Primary metric is `verified`."""

    case_id: str
    detected: bool
    verified: bool  # primary metric: re-run-axe says fix resolves it, no regressions
    confidence: float = 0.0
    explanation: str = ""
    proposed_markup: str = ""
    new_violations: list[str] = field(default_factory=list)
    error: str | None = None  # populated if model call failed (e.g. rate limit)

    @property
    def inconclusive(self) -> bool:
        """True when we couldn't even attempt the eval (no model, rate-limited, etc)."""
        return self.error is not None


def load_golden(dir: Path) -> list[GoldenCase]:
    return sorted(
        (GoldenCase.from_path(p) for p in dir.glob("*.json")),
        key=lambda c: c.id,
    )


async def _maybe_pool() -> asyncpg.Pool | None:
    """Optional asyncpg pool for retrieval; None when CURB_TEST_DATABASE_URL absent.
    The agent prompt is still useful without retrieval (just less grounded)."""
    dsn = os.getenv("CURB_TEST_DATABASE_URL")
    if not dsn:
        return None
    return await asyncpg.create_pool(dsn, min_size=1, max_size=2)


async def run_one(case: GoldenCase, *, agent_model: Any) -> EvalResult:
    """Run one golden case end-to-end. `agent_model` is the pydantic-ai
    Model (or FunctionModel) the agent should use.

    A model that raises (rate limit, transient outage) is *inconclusive*:
    `error=…` is set, the case is not counted against the pass rate. The
    agent loop itself swallows the exception inside `propose_and_verify`
    and returns None; we use that signal here.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            page = await browser.new_page()
            await page.set_content(case.fixture_html)

            violations = await run_axe_on_page(uuid4(), page)
            target = next((v for v in violations if v.rule_id == case.expected_rule_id), None)
            if target is None:
                return EvalResult(
                    case_id=case.id,
                    detected=False,
                    verified=False,
                    error=f"detector did not flag {case.expected_rule_id} on this fixture",
                )

            guidance: list[Guidance] = []
            pool = await _maybe_pool()
            if pool is not None:
                try:
                    guidance = await retrieve_for_violation(
                        pool,
                        rule_id=target.rule_id,
                        wcag_criterion=target.wcag_criterion,
                        description=target.description,
                        help_text=target.help,
                        k=3,
                    )
                finally:
                    await pool.close()

            agent = build_agent(agent_model)
            remediation: Remediation | None = await propose_and_verify(
                agent=agent,
                page=page,
                violation=target,
                guidance=guidance,
                model_label="eval",
            )
            await page.close()
        finally:
            await browser.close()

    if remediation is None:
        # Model-side failure (rate limit, transient API error). Inconclusive,
        # not a regression.
        return EvalResult(
            case_id=case.id,
            detected=True,
            verified=False,
            error="model call failed (likely rate limit; see worker logs)",
        )
    return EvalResult(
        case_id=case.id,
        detected=True,
        verified=remediation.verified,
        confidence=remediation.confidence,
        explanation=remediation.explanation,
        proposed_markup=remediation.patch.fixed,
        new_violations=list(remediation.new_violations),
    )


def configured_model() -> Any | None:
    """Build the pydantic-ai Model from env (MODEL_PROVIDER + MODEL_API_KEY).
    Returns None if no key is set, so callers can skip / mark inconclusive."""
    from curb_shared.config import load_settings  # noqa: PLC0415

    s = load_settings()
    choice = resolve(s)
    if choice is None:
        return None
    return build_model(choice)


def _used_violations(result: EvalResult) -> dict[str, Any]:
    """Pluck a JSON-friendly dict out of EvalResult for reporting."""
    return asdict(result)

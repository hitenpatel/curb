"""Primary metric: deterministic re-run-axe pass rate against golden cases.

Each case runs end-to-end:
  fixture → detect → retrieve → agent → validate → verified?

A case passes iff `verified` is True (resolved by axe, no regressions in
the parent region). Inconclusive cases (model rate-limited, API outage)
are not counted against the pass rate — flakiness in a free-tier API
shouldn't block deploy.

The session-level test asserts the pass rate clears
CURB_EVAL_MIN_PASS_RATE (defaults to 1.0). Tune via env in CI if you want
to allow a known-weak case while the corpus or prompt evolves.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

from evals.conftest import write_summary
from evals.runner import GoldenCase, run_one

# Pace the eval to respect the free-tier rate limit (Gemini 2.5 Flash:
# 20 RPM at the time of writing). Each case makes 2-4 model calls, so a
# 4s gap between cases keeps us well under the budget.
INTER_CASE_DELAY_S = float(os.getenv("CURB_EVAL_DELAY_S", "4"))


@pytest.mark.eval
async def test_each_golden_case_verifies(
    model: Any,
    golden_cases: list[GoldenCase],
    results_log: list[dict[str, Any]],
    pass_rate_threshold: float,
) -> None:
    """Run every golden case; assert the conclusive pass rate clears the
    threshold. We DON'T fail on the first miss because the per-case detail
    is useful for diagnosis — collect, then assert at the end."""
    for i, case in enumerate(golden_cases):
        if i > 0:
            await asyncio.sleep(INTER_CASE_DELAY_S)
        result = await run_one(case, agent_model=model)
        results_log.append(
            {
                "case_id": result.case_id,
                "detected": result.detected,
                "verified": result.verified,
                "confidence": result.confidence,
                "error": result.error,
            }
        )
        # Flush after every case so the CI artefact survives a mid-run skip.
        write_summary(results_log)

    conclusive = [r for r in results_log if not r.get("error")]
    if not conclusive:
        pytest.skip("every case was inconclusive (model errors); not a regression")

    passed = sum(1 for r in conclusive if r["verified"])
    rate = passed / len(conclusive)
    assert rate >= pass_rate_threshold, (
        f"pass rate {rate:.0%} ({passed}/{len(conclusive)}) below threshold "
        f"{pass_rate_threshold:.0%}; see evals/.last-run.md"
    )

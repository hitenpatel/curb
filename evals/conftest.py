"""Eval-harness fixtures.

The harness is regular pytest with two extra knobs:
- CURB_EVAL_SUITE = "golden" (default) or "smoke" picks the case directory.
- CURB_EVAL_MIN_PASS_RATE = float in [0, 1]; the suite fails if conclusive
  cases pass below this fraction. 1.0 by default (every case must verify).
- When MODEL_PROVIDER + MODEL_API_KEY aren't set, the suite is skipped
  cleanly rather than failing — the eval gate degrades to a warning, since
  a missing key isn't a regression in the agent.

Inconclusive results (model rate limit, transient error) are excluded from
the pass-rate denominator. We log them but don't fail on them — flakiness
in a free-tier API shouldn't break deploy.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from evals.runner import GoldenCase, configured_model, load_golden

EVAL_ROOT = Path(__file__).parent
SUMMARY_PATH = EVAL_ROOT / "last-run.md"


def _suite_dir() -> Path:
    return EVAL_ROOT / os.getenv("CURB_EVAL_SUITE", "golden")


def write_summary(rows: list[dict[str, Any]]) -> None:
    """Render rows into the Markdown table CI artefacts.

    Called both inside the test body (so a partial run still produces a
    report even if pytest skips at the end) and from the fixture teardown
    (for runs that don't reach the call site). Idempotent overwrite."""
    path = SUMMARY_PATH.resolve()
    if not rows:
        # Empty placeholder so the artifact upload step doesn't warn.
        path.write_text(
            "| case | detected | verified | conf | note |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| (no cases ran) | - | - | - | model fixture skipped |\n"
        )
        print(f"\n[eval] wrote placeholder summary to {path}", flush=True)
        return
    header = "| case | detected | verified | conf | note |\n| --- | --- | --- | --- | --- |\n"
    body = "\n".join(
        f"| {r['case_id']} | {'Y' if r['detected'] else 'N'} | "
        f"{'Y' if r['verified'] else 'N'} | {r['confidence']:.2f} | "
        f"{(r.get('error') or '')[:80]} |"
        for r in rows
    )
    path.write_text(header + body + "\n")
    print(f"\n[eval] wrote {len(rows)}-row summary to {path}", flush=True)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """If no model is configured, deselect the suite cleanly."""
    if configured_model() is not None:
        return
    skip_marker = pytest.mark.skip(
        reason="MODEL_PROVIDER + MODEL_API_KEY not set; eval gate degraded to warning."
    )
    for item in items:
        if "evals/" in str(getattr(item, "fspath", "")):
            item.add_marker(skip_marker)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Always leave a `.last-run.md` behind so CI's artefact upload step
    has a file to upload — placeholder if no results accumulated."""
    if not SUMMARY_PATH.exists():
        write_summary([])


@pytest.fixture(scope="session")
def model() -> Any:
    """The pydantic-ai Model the agent uses for the eval run. Resolved once
    per session so we don't rebuild the client per case."""
    m = configured_model()
    if m is None:
        pytest.skip("MODEL_PROVIDER + MODEL_API_KEY not set")
    return m


@pytest.fixture(scope="session")
def golden_cases() -> list[GoldenCase]:
    cases = load_golden(_suite_dir())
    if not cases:
        pytest.skip(f"no golden cases in {_suite_dir()}")
    return cases


@pytest.fixture(scope="session")
def pass_rate_threshold() -> float:
    return float(os.getenv("CURB_EVAL_MIN_PASS_RATE", "1.0"))


@pytest.fixture(scope="session")
def results_log() -> Iterator[list[dict[str, Any]]]:
    """Accumulator for per-case results; emitted as a Markdown table when
    the session ends. The test body also writes via `write_summary` after
    each case so a session-level skip still leaves an artefact behind."""
    rows: list[dict[str, Any]] = []
    yield rows
    write_summary(rows)

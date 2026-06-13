"""Verified-only contract tests.

The agent uses pydantic-ai's TestModel + FunctionModel to script behaviour
without dialling out to a real LLM. Two things must hold:

1. If the agent never calls `validate`, `verified` must be False after the
   worker post-processes the Remediation — even if the agent claimed True.
2. If validate fires and confirms (resolved=True, no new_violations),
   verified ends up True.

The validate tool itself (Playwright + axe) is exercised in a separate
slow test against a real browser; see test_validate.py.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import curb_worker.agent as agent_mod
import pytest
from curb_shared import Patch, Remediation, ValidationResult, Violation
from curb_worker.agent import build_agent, propose_and_verify
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel


def _make_violation() -> Violation:
    return Violation(
        id=uuid4(),
        audit_id=uuid4(),
        rule_id="image-alt",
        wcag_criterion="1.1.1",
        description="Images must have alternative text",
        help="Provide alt text",
        help_url="https://example.com/image-alt",
        severity="critical",
        selector="img",
        markup='<img src="/x.png">',
        failure_summary="Element has no alt attribute",
    )


def _make_patch() -> Patch:
    return Patch(
        target_selector="img",
        original='<img src="/x.png">',
        fixed='<img src="/x.png" alt="Banner of a Mars rover">',
        unified_diff='-<img src="/x.png">\n+<img src="/x.png" alt="Banner of a Mars rover">',
    )


class _StubPage:
    """We monkey-patch the validate tool to bypass Playwright, but the Page
    object still needs to be present on AgentDeps; this is the bare stand-in."""


@pytest.fixture
def fake_page() -> Any:
    return _StubPage()


async def _liar_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Model that emits a Remediation with verified=True without ever calling validate."""
    patch = _make_patch()
    bogus = Remediation(
        violation_id=uuid4(),
        wcag_criterion="1.1.1",
        severity="critical",
        explanation="just trust me",
        patch=patch,
        confidence=0.99,
        verified=True,
        new_violations=[],
    )
    assert info.output_tools, "Agent must expose a final_result tool for structured output"
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=info.output_tools[0].name,
                args=bogus.model_dump(mode="json"),
            )
        ]
    )


async def _honest_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Model that calls validate, then emits a verified-false Remediation
    (the worker should still respect what validate actually said)."""
    # First turn: call the validate tool. Second turn: emit the final output.
    # info doesn't tell us the turn count, so we inspect the message log.
    has_tool_return = any(
        isinstance(p, ToolReturnPart)
        for m in messages
        if isinstance(m, ModelRequest)
        for p in m.parts
    )
    if not has_tool_return:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="validate",
                    args=_make_patch().model_dump(mode="json"),
                )
            ]
        )
    # Second turn: agent says verified=false, worker should still flip
    # to true based on the validate result that was returned to it.
    patch = _make_patch()
    final = Remediation(
        violation_id=uuid4(),
        wcag_criterion="1.1.1",
        severity="critical",
        explanation="Added alt text per 1.1.1 guidance",
        patch=patch,
        confidence=0.95,
        verified=False,  # honest-but-conservative; worker promotes if validate confirmed
        new_violations=[],
    )
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=info.output_tools[0].name,
                args=final.model_dump(mode="json"),
            ),
            TextPart(content=""),
        ]
    )


async def _stub_browser_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass Playwright for the two helpers propose_and_verify calls."""

    async def _fake_baseline(*_args: object, **_kwargs: object) -> tuple[str, frozenset[str]]:
        return ("body", frozenset())

    monkeypatch.setattr(agent_mod, "baseline_for", _fake_baseline)


async def test_unverified_when_agent_skips_validate(
    fake_page: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _stub_browser_io(monkeypatch)
    violation = _make_violation()
    agent = build_agent(FunctionModel(_liar_function))
    out = await propose_and_verify(
        agent=agent,
        page=fake_page,
        violation=violation,
        guidance=[],
        model_label="test:liar",
    )
    assert out is not None
    assert out.verified is False, "agent skipped validate; worker must override verified to False"


async def test_verified_when_validate_resolved(
    fake_page: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stub the deterministic half of validate (Playwright + axe) so we
    don't need a browser; the contract we're proving is that
    propose_and_verify trusts validate's last result, not the agent's claim."""

    async def _fake_apply(*_args: object, **_kwargs: object) -> ValidationResult:
        return ValidationResult(resolved=True, new_violations=[], notes="")

    await _stub_browser_io(monkeypatch)
    monkeypatch.setattr(agent_mod, "apply_patch_and_check", _fake_apply)

    violation = _make_violation()
    agent = build_agent(FunctionModel(_honest_function))
    out = await propose_and_verify(
        agent=agent,
        page=fake_page,
        violation=violation,
        guidance=[],
        model_label="test:honest",
    )
    assert out is not None
    assert out.verified is True
    assert out.violation_id == violation.id
    assert out.new_violations == []

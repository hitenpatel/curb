"""Playwright + axe-core detection.

Runs a single audit against a URL (or an HTML string, for tests). axe-core is
vendored; we never reach for the CDN at audit time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from curb_shared import Violation, coerce_severity
from playwright.async_api import Browser, BrowserContext, Page

_AXE_BUNDLE = (Path(__file__).parent / "vendor" / "axe.min.js").read_text()

# Run only the rules tied to WCAG 2.x A/AA criteria — the agent's job is to
# fix things people actually fail compliance on, not best-practice nudges.
_AXE_OPTIONS: dict[str, Any] = {
    "runOnly": {
        "type": "tag",
        "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
    },
    "resultTypes": ["violations"],
}


def _wcag_criterion(tags: list[str]) -> str:
    """Lift the WCAG criterion id out of axe's tag list.

    axe emits tags like ['cat.text-alternatives', 'wcag2a', 'wcag111', 'TTv5'].
    'wcag111' means SC 1.1.1; we expand it to '1.1.1'.
    """
    # 'wcag111' (3-digit) -> '1.1.1'; 'wcag1411' (4-digit) -> '1.4.11'.
    prefix = "wcag"
    three_digit, four_digit = 3, 4
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        digits = tag[len(prefix) :]
        if not digits.isdigit():
            continue
        if len(digits) == three_digit:
            return ".".join(digits)
        if len(digits) == four_digit:
            return f"{digits[0]}.{digits[1]}.{digits[2:]}"
    return "unknown"


def _parse_axe_results(audit_id: UUID, raw: dict[str, Any]) -> list[Violation]:
    """Flatten axe's nested violation/node structure into our Violation rows."""
    out: list[Violation] = []
    for v in raw.get("violations", []):
        tags = cast(list[str], v.get("tags", []))
        criterion = _wcag_criterion(tags)
        for node in v.get("nodes", []):
            # axe gives target as an array (to address shadow / iframe depth);
            # join with ' >>> ' so we keep the path round-trippable.
            target = node.get("target", [])
            selector = " >>> ".join(target) if isinstance(target, list) else str(target)
            out.append(
                Violation(
                    id=uuid4(),
                    audit_id=audit_id,
                    rule_id=v["id"],
                    wcag_criterion=criterion,
                    description=v.get("description", ""),
                    help=v.get("help", ""),
                    help_url=v.get("helpUrl", ""),
                    severity=coerce_severity(v.get("impact")),
                    selector=selector,
                    markup=node.get("html", ""),
                    failure_summary=node.get("failureSummary", ""),
                )
            )
    return out


async def run_axe_on_page(audit_id: UUID, page: Page) -> list[Violation]:
    """Inject axe-core into a loaded page and return Curb violations.

    Caller owns the page lifecycle. We only inject + evaluate.
    """
    await page.add_script_tag(content=_AXE_BUNDLE)
    raw = await page.evaluate(
        "async (opts) => await axe.run(document, opts)",
        _AXE_OPTIONS,
    )
    return _parse_axe_results(audit_id, raw)


async def audit_url(audit_id: UUID, url: str, browser: Browser) -> list[Violation]:
    """Open the URL in a fresh context, wait for it to settle, run axe."""
    context: BrowserContext = await browser.new_context()
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        return await run_axe_on_page(audit_id, page)
    finally:
        await context.close()

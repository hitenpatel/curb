"""End-to-end detection tests against fixture HTML pages.

Marked `slow` so the pre-push hook skips them; CI runs them after
`playwright install chromium`.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from curb_worker.detector import _parse_axe_results, _wcag_criterion, run_axe_on_page
from playwright.async_api import Browser


def test_wcag_criterion_three_digit() -> None:
    assert _wcag_criterion(["cat.text-alternatives", "wcag2a", "wcag111"]) == "1.1.1"


def test_wcag_criterion_four_digit() -> None:
    assert _wcag_criterion(["wcag2aa", "wcag1411"]) == "1.4.11"


def test_wcag_criterion_unknown_when_absent() -> None:
    assert _wcag_criterion(["cat.aria", "best-practice"]) == "unknown"


def test_parse_axe_flattens_nodes_to_violations() -> None:
    audit_id = uuid4()
    raw = {
        "violations": [
            {
                "id": "image-alt",
                "impact": "Critical",
                "tags": ["wcag2a", "wcag111"],
                "description": "Images must have alternative text",
                "help": "Add alt text",
                "helpUrl": "https://dequeuniversity.com/rules/axe/4.10/image-alt",
                "nodes": [
                    {
                        "target": ["img"],
                        "html": '<img src="/x.png">',
                        "failureSummary": "Fix this",
                    },
                    {
                        "target": ["img.hero"],
                        "html": '<img class="hero" src="/y.png">',
                        "failureSummary": "Fix that",
                    },
                ],
            },
        ]
    }
    out = _parse_axe_results(audit_id, raw)
    assert len(out) == 2
    assert {v.selector for v in out} == {"img", "img.hero"}
    assert all(v.rule_id == "image-alt" for v in out)
    assert all(v.wcag_criterion == "1.1.1" for v in out)
    assert all(v.severity == "critical" for v in out)
    assert all(v.audit_id == audit_id for v in out)


@pytest.mark.slow
async def test_detector_catches_known_violations(browser: Browser, known_bad_page: str) -> None:
    audit_id = uuid4()
    page = await browser.new_page()
    await page.set_content(known_bad_page)
    violations = await run_axe_on_page(audit_id, page)
    await page.close()

    rule_ids = {v.rule_id for v in violations}
    assert "image-alt" in rule_ids, f"axe missed image-alt; got {rule_ids}"
    assert "button-name" in rule_ids, f"axe missed button-name; got {rule_ids}"
    assert "html-has-lang" in rule_ids, f"axe missed html-has-lang; got {rule_ids}"

    image_alt = next(v for v in violations if v.rule_id == "image-alt")
    assert image_alt.wcag_criterion.startswith("1.1.1")
    assert image_alt.severity in {"critical", "serious"}
    assert "<img" in image_alt.markup
    assert image_alt.help_url.startswith("https://")


@pytest.mark.slow
async def test_detector_clean_page_yields_no_violations(browser: Browser) -> None:
    audit_id = uuid4()
    page = await browser.new_page()
    await page.set_content(
        """<!DOCTYPE html>
<html lang="en">
<head><title>Clean</title></head>
<body>
  <h1>Hello</h1>
  <p>This page should pass axe.</p>
</body>
</html>"""
    )
    violations = await run_axe_on_page(audit_id, page)
    await page.close()
    assert violations == []

"""End-to-end test of the validate tool's deterministic half.

Loads a tiny HTML fixture in Chromium, runs detection to get a real
Violation + selector, then applies a patch and checks axe agrees the
violation is gone. Marked `slow` since it needs Chromium.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from curb_worker.detector import run_axe_on_page
from curb_worker.validate import apply_patch_and_check, baseline_for
from playwright.async_api import Browser

pytestmark = pytest.mark.slow


_BAD = """<!DOCTYPE html>
<html lang="en">
<head><title>Validate me</title></head>
<body>
  <main>
    <img id="hero" src="/x.png">
  </main>
</body>
</html>"""


async def test_apply_patch_resolves_image_alt(browser: Browser) -> None:
    page = await browser.new_page()
    await page.set_content(_BAD)

    # Detect the offending img.
    violations = await run_axe_on_page(uuid4(), page)
    img_alt = next(v for v in violations if v.rule_id == "image-alt")
    assert img_alt.selector, "axe should give us a selector for the offending img"

    # Snapshot the parent region before the patch.
    _, baseline = await baseline_for(page, img_alt)
    assert "image-alt" in baseline  # the baseline itself flags it; that's the bug

    # Apply a sensible fix.
    fixed = '<img id="hero" src="/x.png" alt="A photo of the hero of this story">'
    result = await apply_patch_and_check(
        page,
        target_selector=img_alt.selector,
        fixed_markup=fixed,
        original_rule_id="image-alt",
        baseline_rule_ids=baseline,
    )
    await page.close()

    assert result.resolved is True, result.notes
    assert result.new_violations == [], f"unexpected regressions: {result.new_violations}"


async def test_apply_patch_unresolved_when_fix_is_wrong(browser: Browser) -> None:
    """A 'fix' that doesn't actually address the violation must not be marked resolved."""
    page = await browser.new_page()
    await page.set_content(_BAD)

    violations = await run_axe_on_page(uuid4(), page)
    img_alt = next(v for v in violations if v.rule_id == "image-alt")
    _, baseline = await baseline_for(page, img_alt)

    # Same img, no alt — still broken.
    fixed = '<img id="hero" src="/y.png">'
    result = await apply_patch_and_check(
        page,
        target_selector=img_alt.selector,
        fixed_markup=fixed,
        original_rule_id="image-alt",
        baseline_rule_ids=baseline,
    )
    await page.close()

    assert result.resolved is False
    assert "image-alt" in result.notes

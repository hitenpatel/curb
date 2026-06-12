"""Worker test fixtures.

The detection tests need a real Chromium. We boot one per session and reuse
across tests; per-test isolation comes from BrowserContext.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from playwright.async_api import Browser, async_playwright


@pytest_asyncio.fixture(scope="function")
async def browser() -> AsyncIterator[Browser]:
    """A headless Chromium for one test. Function-scoped so the asyncio loop
    matches pytest-asyncio's default scope; cheap because Chromium is preloaded
    in the Playwright Docker image / via `playwright install` in CI."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        yield browser
        await browser.close()


@pytest.fixture
def known_bad_page() -> str:
    """Tiny HTML page with axe-detectable WCAG failures.

    Issues planted:
    - <img> with no alt → image-alt (1.1.1)
    - <button> with empty accessible name → button-name (4.1.2)
    - form <input> with no label → label (1.3.1 / 4.1.2)
    - <html> with no lang → html-has-lang (3.1.1)
    """
    return """<!DOCTYPE html>
<html>
<head><title>Known bad</title></head>
<body>
  <h1>Known bad</h1>
  <img src="/x.png">
  <button></button>
  <form><input type="text" name="q"></form>
</body>
</html>"""

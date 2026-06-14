"""Curb audits Curb.

Phase 5 requires the app to meet the bar it enforces. We boot the built
Node adapter output, point Playwright + axe at the home page, and assert
zero WCAG A/AA violations. Marked `slow` because it spins up a Node server.
"""

from __future__ import annotations

import os
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from curb_worker.detector import run_axe_on_page
from playwright.async_api import Browser, async_playwright

pytestmark = pytest.mark.slow

WEB_DIR = Path(__file__).resolve().parents[1]
BUILD_DIR = WEB_DIR / "build"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError(f"port {port} never opened")


@pytest.fixture(scope="module")
def web_server() -> Iterator[str]:
    if not BUILD_DIR.exists():
        pytest.skip("apps/web/build is not built; run `pnpm --dir apps/web build` first.")
    port = _free_port()
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["HOST"] = "127.0.0.1"
    env["ORIGIN"] = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        ["node", str(BUILD_DIR)],
        cwd=WEB_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_port(port)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest_asyncio.fixture
async def browser_for_app() -> Browser:  # type: ignore[misc]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            yield browser
        finally:
            await browser.close()


async def test_home_page_passes_axe(web_server: str, browser_for_app: Browser) -> None:
    page = await browser_for_app.new_page()
    await page.goto(web_server, wait_until="networkidle")
    violations = await run_axe_on_page(uuid4(), page)
    await page.close()
    # Surface any violations in the assertion message so a regression is
    # diagnosable from the CI log without an artefact.
    lines = "\n".join(
        f"  - {v.rule_id} ({v.wcag_criterion}, {v.severity}): {v.selector}" for v in violations
    )
    assert violations == [], f"Curb's home page failed axe ({len(violations)} violations):\n{lines}"

"""Retrieval relevance tests.

These need a Postgres with the wcag_chunks corpus ingested. The CI runner
spins up Postgres as a service and re-runs the ingest before pytest;
locally point CURB_TEST_DATABASE_URL at a populated DB.

Marked `slow` so the pre-push hook can skip without setup.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
from curb_worker.retrieval import retrieve_for_violation, retrieve_guidance

pytestmark = pytest.mark.slow

DSN = os.getenv("CURB_TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(DSN is None, reason="CURB_TEST_DATABASE_URL not set")


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    assert DSN is not None
    p = await asyncpg.create_pool(DSN, min_size=1, max_size=2)
    try:
        yield p
    finally:
        await p.close()


@needs_db
async def test_retrieves_image_alt_guidance_for_1_1_1(pool: asyncpg.Pool) -> None:
    out = await retrieve_for_violation(
        pool,
        rule_id="image-alt",
        wcag_criterion="1.1.1",
        description="Images must have alternative text",
        help_text="Ensure <img> elements have alternate text",
        k=3,
    )
    assert out, "retrieval returned nothing"
    top = out[0]
    # Top result should be the 1.1.1 chunk (criterion boost + semantic match).
    assert top.criterion == "1.1.1", f"top hit was {top.criterion}: {top.title}"
    assert "alt" in top.body.lower()


@needs_db
async def test_retrieves_name_role_value_guidance_for_4_1_2(pool: asyncpg.Pool) -> None:
    out = await retrieve_for_violation(
        pool,
        rule_id="button-name",
        wcag_criterion="4.1.2",
        description="Buttons must have discernible text",
        help_text="Ensure buttons have discernible text",
        k=3,
    )
    assert out
    top_criteria = {g.criterion for g in out}
    assert "4.1.2" in top_criteria, f"no 4.1.2 in top hits; got {top_criteria}"
    # At least one hit should mention buttons / button-name.
    bodies = " ".join(g.body.lower() for g in out)
    assert "button" in bodies


@needs_db
async def test_retrieves_color_contrast_for_1_4_3(pool: asyncpg.Pool) -> None:
    out = await retrieve_for_violation(
        pool,
        rule_id="color-contrast",
        wcag_criterion="1.4.3",
        description="Elements must meet minimum colour contrast ratio thresholds",
        help_text="Foreground and background colours must have sufficient contrast",
        k=3,
    )
    assert out
    assert out[0].criterion == "1.4.3", f"top hit was {out[0].criterion}"
    assert "contrast" in out[0].body.lower()


@needs_db
async def test_criterion_boost_is_applied(pool: asyncpg.Pool) -> None:
    """A vague query that doesn't match strongly should still surface the
    target criterion when we name it, because of the criterion-match boost."""
    out = await retrieve_guidance(
        pool,
        query="something is wrong with this control",
        criterion="3.1.1",
        k=5,
    )
    crits = [g.criterion for g in out]
    assert "3.1.1" in crits, f"criterion-boost didn't surface 3.1.1; got {crits}"

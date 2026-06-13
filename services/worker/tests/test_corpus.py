"""Corpus chunking tests.

The ingestion + retrieval are exercised end-to-end against a real Postgres
in the e2e smoke (see scripts/smoke_retrieval.py). Here we cover the static
chunking + criterion-mapping logic that doesn't need a DB.
"""

from __future__ import annotations

import sys
from pathlib import Path

# corpus/ is at the repo root, not on the package path; add it for tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from corpus.ingest import _aria_chunks, _wcag_chunks, load_chunks


def test_wcag_chunks_cover_top_rules() -> None:
    """The criteria axe-core emits in real-world audits must all be in the corpus."""
    chunks = load_chunks()
    criteria = {c["criterion"] for c in chunks}
    # The set of WCAG SCs the smoke audit hit on Deque Mars + example.com.
    expected = {"1.1.1", "1.4.3", "2.4.4", "2.5.8", "3.1.1", "4.1.2"}
    missing = expected - criteria
    assert not missing, f"corpus is missing guidance for {missing}"


def test_wcag_chunks_body_mentions_axe_rule_when_known() -> None:
    """A chunk for 1.1.1 should mention image-alt so retrieval keys on rule_id work."""
    wcag = _wcag_chunks(
        {
            "source": "test",
            "criteria": [
                {
                    "criterion": "1.1.1",
                    "title": "Non-text Content",
                    "level": "A",
                    "what": "x",
                    "how_to_meet": "y",
                    "common_failures": "z",
                    "axe_rules": ["image-alt"],
                }
            ],
        }
    )
    assert "image-alt" in wcag[0]["body"]
    assert wcag[0]["title"].startswith("1.1.1")


def test_aria_chunks_explode_by_criterion_hint() -> None:
    """A pattern with N criterion hints should yield N chunks (one per criterion)."""
    aria = _aria_chunks(
        {
            "source": "test",
            "patterns": [
                {
                    "pattern": "button",
                    "title": "Button Pattern",
                    "criterion_hints": ["4.1.2", "2.1.1"],
                    "what": "x",
                    "how_to_meet": "y",
                    "common_failures": "z",
                    "snippet": "<button>",
                }
            ],
        }
    )
    criteria = sorted(c["criterion"] for c in aria)
    assert criteria == ["2.1.1", "4.1.2"]
    for c in aria:
        assert c["title"].startswith("ARIA")
        assert "Button" in c["title"]

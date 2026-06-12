from uuid import uuid4

import pytest
from curb_shared import Patch, Remediation, coerce_severity
from pydantic import ValidationError


def test_remediation_defaults_unverified() -> None:
    patch = Patch(
        target_selector="img.hero",
        original='<img class="hero" src="/x.png">',
        fixed='<img class="hero" src="/x.png" alt="Decorative banner">',
        unified_diff="--- a\n+++ b\n",
    )
    remediation = Remediation(
        violation_id=uuid4(),
        wcag_criterion="1.1.1 Non-text Content",
        severity="serious",
        explanation="Add alt text.",
        patch=patch,
        confidence=0.9,
    )
    assert remediation.verified is False
    assert remediation.new_violations == []


def test_confidence_bounds_enforced() -> None:
    patch = Patch(target_selector="a", original="x", fixed="y", unified_diff="")
    with pytest.raises(ValidationError):
        Remediation(
            violation_id=uuid4(),
            wcag_criterion="1.1.1",
            severity="minor",
            explanation="x",
            patch=patch,
            confidence=1.5,
        )


@pytest.mark.parametrize(
    "impact, expected",
    [
        ("critical", "critical"),
        ("Serious", "serious"),
        ("MODERATE", "moderate"),
        ("minor", "minor"),
        (None, "minor"),
        ("unknown", "minor"),
    ],
)
def test_severity_coercion(impact: str | None, expected: str) -> None:
    assert coerce_severity(impact) == expected

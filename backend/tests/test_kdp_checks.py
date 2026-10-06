"""Focused regressions for KDP validation check behavior."""

from uuid import uuid4

from models.assets import BookSettings
from services.kdp.engine import MIN_MARGIN_INCHES, KDPValidator


def test_margin_below_kdp_minimum_returns_an_actionable_issue() -> None:
    settings = BookSettings(
        book_id=uuid4(),
        margin_top=0.75,
        margin_bottom=0.75,
        margin_left=MIN_MARGIN_INCHES - 0.01,
        margin_right=0.75,
    )
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    passed: list[dict[str, object]] = []

    KDPValidator()._check_margins(settings, issues, warnings, passed)

    assert len(issues) == 1
    assert "Left margin" in issues[0]["message"]
    assert "recommendation" in issues[0]

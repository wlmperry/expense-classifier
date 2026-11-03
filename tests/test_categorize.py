"""Tests for the baseline rule-based category classifier.

These run standalone, with no database, since classify() is a pure
function over plain strings.
"""

import pytest

from app.categorize import CATEGORIES, classify


@pytest.mark.parametrize(
    ("merchant", "expected"),
    [
        ("STARBUCKS #1234", "Food & Dining"),
        ("Uber Technologies", "Transportation"),
        ("COMCAST CABLE", "Housing & Utilities"),
        ("AMAZON.COM", "Shopping"),
        ("NETFLIX.COM", "Entertainment"),
        ("CVS PHARMACY #456", "Health & Fitness"),
    ],
)
def test_classify_matches_known_merchant_keywords(merchant, expected):
    assert classify(merchant) == expected


def test_classify_is_case_insensitive():
    assert classify("starbucks coffee") == "Food & Dining"


def test_classify_falls_back_to_other_for_unknown_merchant(merchant="XYZ Widgets Inc"):
    assert classify(merchant) == "Other"


def test_classify_checks_description_too():
    assert classify("Local Shop", description="bought concert tickets") == "Entertainment"


def test_classify_always_returns_an_allowed_category():
    for merchant in ["Starbucks", "Uber", "Comcast", "Amazon", "Netflix", "CVS", "Unknown Co"]:
        assert classify(merchant) in CATEGORIES

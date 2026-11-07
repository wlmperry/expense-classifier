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


@pytest.mark.parametrize(
    ("merchant", "description"),
    [
        ("Barnes & Noble", ""),  # "bar" must not match inside "Barnes"
        ("XYZ Logistics", "delivery confirmation"),  # "deli" must not match "delivery"
        ("Las Vegas Hotel", ""),  # "gas" must not match inside "Vegas"
        ("Current", ""),  # "rent" must not match inside "Current"
    ],
)
def test_classify_does_not_match_a_keyword_inside_an_unrelated_word(merchant, description):
    assert classify(merchant, description) == "Other"


def test_classify_still_matches_a_keyword_that_is_a_whole_word():
    assert classify("Corner Bar") == "Food & Dining"
    assert classify("Shell Gas Station") == "Transportation"


def test_classify_matches_a_keyword_ending_in_a_non_word_character():
    assert classify("Disney+ Subscription") == "Entertainment"

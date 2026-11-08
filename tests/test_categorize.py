"""Tests for the baseline rule-based category classifier.

These run standalone, with no database, since classify() is a pure
function over plain strings.
"""

from decimal import Decimal

import pytest

from app.categorize import CATEGORIES, classify, classify_with_confidence


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


def test_confidence_is_low_for_no_match():
    assert classify_with_confidence("XYZ Widgets Inc") == ("Other", Decimal("0.2"))


def test_confidence_is_medium_for_a_single_keyword_hit():
    # "starbucks" is the only keyword that matches anywhere.
    assert classify_with_confidence("Starbucks") == ("Food & Dining", Decimal("0.75"))


def test_confidence_is_high_for_multiple_keyword_hits_in_one_category():
    # "cvs" and "pharmacy" both match, both within Health & Fitness.
    assert classify_with_confidence("CVS Pharmacy") == ("Health & Fitness", Decimal("0.9"))


def test_confidence_is_ambiguous_for_keyword_hits_in_multiple_categories():
    # "target" matches Shopping, "pharmacy" matches Health & Fitness.
    # Shopping is returned (first by rule order), same category classify()
    # would already have picked, but at the lower ambiguous-match score.
    assert classify_with_confidence("Target Pharmacy") == ("Shopping", Decimal("0.5"))


def test_classify_matches_classify_with_confidences_category():
    for merchant in ["Starbucks", "Target Pharmacy", "Unknown Co", "CVS Pharmacy"]:
        assert classify(merchant) == classify_with_confidence(merchant)[0]


def test_confidence_ignores_a_shorter_match_nested_inside_a_longer_one():
    # "united airlines" is itself a keyword, and it contains a standalone
    # "airlines" match -- that nested match must not count as a second,
    # independent hit and inflate this past a single-keyword match.
    assert classify_with_confidence("United Airlines") == ("Transportation", Decimal("0.75"))


def test_confidence_ignores_a_cross_category_match_nested_inside_a_longer_one():
    # "uber eats" (Food & Dining) contains a standalone "uber" (Transportation)
    # match -- that nested match must not make this look ambiguous.
    assert classify_with_confidence("Uber Eats") == ("Food & Dining", Decimal("0.75"))

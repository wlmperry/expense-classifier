"""Tests for the baseline rule-based category classifier.

These run standalone, with no database, since classify() is a pure
function over plain strings.
"""

from decimal import Decimal

import pytest

from app.categorize import (
    _KEYWORD_RULES,
    CATEGORIES,
    classify,
    classify_with_confidence,
)


def test_every_keyword_rule_names_an_allowed_category():
    # A typo here would make classify() return a name the API's Literal and
    # the database's check constraint both reject, and it would only show
    # up once a real expense happened to match that rule.
    for category, _ in _KEYWORD_RULES:
        assert category in CATEGORIES


def test_every_category_except_other_has_a_keyword_rule():
    rule_categories = [category for category, _ in _KEYWORD_RULES]
    assert len(rule_categories) == len(set(rule_categories))
    assert set(rule_categories) == set(CATEGORIES) - {"Other"}


@pytest.mark.parametrize(
    ("merchant", "expected"),
    [
        ("KROGER #512", "Groceries"),
        ("Joe's Pizza", "Restaurants & Bars"),
        ("STARBUCKS #1234", "Coffee Shops"),
        ("DOORDASH*ORDER", "Food Delivery"),
        ("CHEVRON 0091", "Gas & Fuel"),
        ("Uber Technologies", "Rideshare & Transit"),
        ("AMTRAK TICKETS", "Travel"),
        ("Oak St Landlord LLC", "Rent & Mortgage"),
        ("COMCAST CABLE", "Utilities"),
        ("AMAZON.COM", "Online Shopping"),
        ("WALMART SUPERCENTER", "General Merchandise"),
        ("BEST BUY #77", "Electronics"),
        ("NIKE FACTORY", "Clothing"),
        ("NETFLIX.COM", "Streaming & Subscriptions"),
        ("AMC Cinema 12", "Movies & Events"),
        ("STEAM PURCHASE", "Gaming"),
        ("CVS #456", "Pharmacy"),
        ("Planet Fitness", "Gym & Fitness"),
        ("Bright Smile Dental", "Medical"),
        ("XYZ Widgets Inc", "Other"),
    ],
)
def test_classify_matches_known_merchant_keywords(merchant, expected):
    assert classify(merchant) == expected


def test_classify_is_case_insensitive():
    assert classify("starbucks coffee") == "Coffee Shops"


def test_classify_falls_back_to_other_for_unknown_merchant(merchant="XYZ Widgets Inc"):
    assert classify(merchant) == "Other"


def test_classify_checks_description_too():
    assert classify("Local Shop", description="bought concert tickets") == "Movies & Events"


def test_classify_always_returns_an_allowed_category():
    for merchant in ["Starbucks", "Uber", "Comcast", "Amazon", "Netflix", "CVS", "Unknown Co"]:
        assert classify(merchant) in CATEGORIES


@pytest.mark.parametrize(
    ("merchant", "description"),
    [
        ("Barnes & Noble", ""),  # "bar" must not match inside "Barnes"
        ("XYZ Logistics", "delivery confirmation"),  # "deli" must not match "delivery"
        ("Las Vegas Souvenirs", ""),  # "gas" must not match inside "Vegas"
        ("Current", ""),  # "rent" must not match inside "Current"
    ],
)
def test_classify_does_not_match_a_keyword_inside_an_unrelated_word(merchant, description):
    assert classify(merchant, description) == "Other"


def test_classify_still_matches_a_keyword_that_is_a_whole_word():
    assert classify("Corner Bar") == "Restaurants & Bars"
    assert classify("Shell Gas Station") == "Gas & Fuel"


def test_classify_matches_a_keyword_ending_in_a_non_word_character():
    assert classify("Disney+ Subscription") == "Streaming & Subscriptions"


def test_confidence_is_low_for_no_match():
    assert classify_with_confidence("XYZ Widgets Inc") == ("Other", Decimal("0.2"))


def test_confidence_is_medium_for_a_single_keyword_hit():
    # "starbucks" is the only keyword that matches anywhere.
    assert classify_with_confidence("Starbucks") == ("Coffee Shops", Decimal("0.75"))


def test_confidence_is_high_for_multiple_keyword_hits_in_one_category():
    # "cvs" and "pharmacy" both match, both within Pharmacy.
    assert classify_with_confidence("CVS Pharmacy") == ("Pharmacy", Decimal("0.9"))


def test_confidence_is_ambiguous_for_keyword_hits_in_multiple_categories():
    # "target" matches General Merchandise, "pharmacy" matches Pharmacy.
    # General Merchandise is returned (first by rule order), same category
    # classify() would already have picked, but at the lower ambiguous-match
    # score.
    assert classify_with_confidence("Target Pharmacy") == (
        "General Merchandise",
        Decimal("0.5"),
    )


def test_rule_order_breaks_a_tie_between_specific_categories():
    # "kroger" and "grocery" match Groceries, "store" matches General
    # Merchandise as a separate word. Groceries is listed first, so it wins,
    # at the ambiguous-match score.
    assert classify_with_confidence("Kroger Grocery Store") == ("Groceries", Decimal("0.5"))


def test_classify_matches_classify_with_confidences_category():
    for merchant in ["Starbucks", "Target Pharmacy", "Unknown Co", "CVS Pharmacy"]:
        assert classify(merchant) == classify_with_confidence(merchant)[0]


def test_confidence_ignores_a_shorter_match_nested_inside_a_longer_one():
    # "united airlines" is itself a keyword, and it contains a standalone
    # "airlines" match -- that nested match must not count as a second,
    # independent hit and inflate this past a single-keyword match.
    assert classify_with_confidence("United Airlines") == ("Travel", Decimal("0.75"))


def test_confidence_ignores_a_cross_category_match_nested_inside_a_longer_one():
    # "uber eats" (Food Delivery) contains a standalone "uber" (Rideshare &
    # Transit) match -- that nested match must not make this look ambiguous.
    assert classify_with_confidence("Uber Eats") == ("Food Delivery", Decimal("0.75"))


def test_a_longer_keyword_beats_a_generic_one_nested_inside_it():
    # "apple store" (Electronics) contains "store" (General Merchandise).
    # The nested "store" is discarded, so this is a clean Electronics match,
    # not a tie.
    assert classify_with_confidence("Apple Store") == ("Electronics", Decimal("0.75"))


def test_confidence_counts_a_repeated_keyword_once_not_twice():
    # The same keyword appearing in both merchant and description (common
    # for Plaid imports, where both fields can echo the same text) must
    # not look more confident than it would with only one of them set.
    assert classify_with_confidence("Starbucks", "Starbucks") == (
        "Coffee Shops",
        Decimal("0.75"),
    )
    assert classify_with_confidence("Starbucks", "STARBUCKS #1234") == (
        "Coffee Shops",
        Decimal("0.75"),
    )

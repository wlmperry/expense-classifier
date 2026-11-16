"""Tests for the ML classifier and the hybrid categorizer (Issue #55)."""

from decimal import Decimal

import pytest
from sklearn.model_selection import train_test_split

from app import ml_classifier
from app.categorize import Categorization, categorize, classify_with_confidence
from app.ml_classifier import load_training_data, normalize, train_model

# --- The hybrid order ---


def test_rules_decide_when_a_keyword_matches():
    result = categorize("Starbucks", "STARBUCKS #221")

    assert result == Categorization("Coffee Shops", Decimal("0.75"), source="rules")


@pytest.mark.parametrize(
    ("merchant", "description", "expected"),
    [
        # In the training data, under a different store number and city.
        ("Dunkin", "DUNKIN #4412 MIAMI FL", "Coffee Shops"),
        # Not in the training data at all: recognized from descriptive words.
        ("Luigi's Pizzeria", "LUIGIS PIZZERIA", "Restaurants & Bars"),
        ("Valley Petro", "VALLEY PETRO DIESEL", "Gas & Fuel"),
        ("Sunrise Yoga", "SUNRISE YOGA STUDIO", "Gym & Fitness"),
    ],
)
def test_the_model_categorizes_merchants_the_rules_miss(merchant, description, expected):
    assert classify_with_confidence(merchant, description)[0] == "Other"  # rules alone miss it

    result = categorize(merchant, description)

    assert result.category == expected
    assert result.source == "model"
    assert Decimal("0.2") <= result.confidence <= 1


def test_an_unsure_model_guess_falls_back_to_other(monkeypatch):
    monkeypatch.setattr(ml_classifier, "predict", lambda *_: ("Gaming", Decimal("0.19")))

    result = categorize("Something Unknown", "")

    assert result == Categorization("Other", Decimal("0.2"), source=None)


def test_a_confident_model_guess_at_the_threshold_is_used(monkeypatch):
    monkeypatch.setattr(ml_classifier, "predict", lambda *_: ("Gaming", Decimal("0.2")))

    result = categorize("Something Unknown", "")

    assert result == Categorization("Gaming", Decimal("0.2"), source="model")


def test_a_model_guess_of_other_has_no_source(monkeypatch):
    monkeypatch.setattr(ml_classifier, "predict", lambda *_: ("Other", Decimal("0.9")))

    result = categorize("Venmo", "VENMO PAYMENT")

    assert result == Categorization("Other", Decimal("0.2"), source=None)


def test_classify_with_confidence_still_uses_the_rules_only():
    # Migration 3c86f19d4985 depends on this staying rules-only.
    assert classify_with_confidence("Dunkin", "DUNKIN #4412") == ("Other", Decimal("0.2"))
    assert classify_with_confidence("Starbucks") == ("Coffee Shops", Decimal("0.75"))


# --- The model itself ---


def test_normalize_drops_digits_and_symbols_and_lowercases():
    assert normalize("DUNKIN #3321", "ATLANTA GA 30303") == "dunkin atlanta ga"


def test_training_data_covers_every_category_with_enough_examples():
    from app.categorize import CATEGORIES

    _, categories = load_training_data()

    assert set(categories) == set(CATEGORIES)
    assert min(categories.count(category) for category in CATEGORIES) >= 15


def test_training_is_deterministic():
    texts, categories = load_training_data()
    first = train_model(texts, categories)
    second = train_model(texts, categories)
    sample = ["luigis pizzeria", "valley petro diesel", "xqz"]

    assert (first.predict_proba(sample) == second.predict_proba(sample)).all()


def test_accuracy_on_held_back_examples_stays_above_a_floor():
    """Guards against a training-data or settings change that quietly makes
    the model worse. Same split as scripts/evaluate_classifier.py, which
    measured 53% when this test was written (random guessing is about 5%)."""
    texts, categories = load_training_data()
    train_texts, test_texts, train_categories, test_categories = train_test_split(
        texts, categories, test_size=0.25, random_state=0, stratify=categories
    )
    model = train_model(train_texts, train_categories)

    accuracy = (model.predict(test_texts) == test_categories).mean()

    assert accuracy >= 0.45


# --- Through the API ---


def _create(client, merchant: str, description: str, **extra) -> dict:
    response = client.post(
        "/expenses",
        json={
            "merchant": merchant,
            "description": description,
            "amount": "4.50",
            "expense_date": "2026-11-16",
            **extra,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_api_reports_a_model_categorization(client):
    body = _create(client, "Valley Petro", "VALLEY PETRO DIESEL")

    assert body["category"] == "Gas & Fuel"
    assert body["category_source"] == "model"


def test_api_reports_a_rules_categorization(client):
    body = _create(client, "Starbucks", "Latte")

    assert body["category"] == "Coffee Shops"
    assert body["category_source"] == "rules"


def test_api_has_no_source_when_a_person_picks_the_category(client):
    body = _create(client, "Valley Petro", "VALLEY PETRO DIESEL", category="Travel")

    assert body["category_source"] is None
    assert body["confidence"] is None


def test_api_clears_the_source_when_a_person_changes_the_category(client):
    created = _create(client, "Valley Petro", "VALLEY PETRO DIESEL")

    response = client.patch(f"/expenses/{created['id']}", json={"category": "Travel"})

    assert response.json()["category_source"] is None
    assert response.json()["confidence"] is None

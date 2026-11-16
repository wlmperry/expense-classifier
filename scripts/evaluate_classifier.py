"""Measure how well the ML classifier does on examples it has never seen
(Issue #55). Run from the repository root:

    python -m scripts.evaluate_classifier

A model can't be judged on its own training examples, since it may just have
memorized them. So this holds back a quarter of app/training_data.csv as a
test set, trains a fresh model on the other three quarters, and scores it on
the held-back quarter only. The split is stratified (every category keeps
the same share in both parts) and seeded, so every run gives the same
numbers.

The deployed model (app/ml_classifier.get_model()) is trained on all of the
examples, so it should do at least as well as the numbers printed here.
"""

from decimal import Decimal

from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

from app.categorize import MIN_MODEL_CONFIDENCE
from app.ml_classifier import load_training_data, train_model

TEST_SHARE = 0.25
RANDOM_SEED = 0


def main() -> None:
    texts, categories = load_training_data()
    train_texts, test_texts, train_categories, test_categories = train_test_split(
        texts,
        categories,
        test_size=TEST_SHARE,
        random_state=RANDOM_SEED,
        stratify=categories,
    )
    model = train_model(train_texts, train_categories)

    predictions = model.predict(test_texts)
    best_probabilities = model.predict_proba(test_texts).max(axis=1)

    print(f"Examples: {len(texts)} ({len(train_texts)} to train, {len(test_texts)} held back to test)")
    print(f"Accuracy on the held-back examples: {accuracy_score(test_categories, predictions):.0%}")
    print()
    print("Per category (precision: how often a guess of this category was right;")
    print("recall: how many of this category's examples were found):")
    print(classification_report(test_categories, predictions, zero_division=0))

    print("Confidence threshold trade-off on the held-back examples:")
    print("  threshold  answered  right when answered")
    for threshold in (0.0, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5):
        answered = [
            (predicted, actual)
            for predicted, actual, probability in zip(
                predictions, test_categories, best_probabilities, strict=True
            )
            if probability >= threshold
        ]
        right = sum(predicted == actual for predicted, actual in answered)
        accuracy = right / len(answered) if answered else 0
        marker = "  <- used by the app" if Decimal(str(threshold)) == MIN_MODEL_CONFIDENCE else ""
        print(f"  {threshold:>9.2f}  {len(answered) / len(test_texts):>8.0%}  {accuracy:>19.0%}{marker}")


if __name__ == "__main__":
    main()

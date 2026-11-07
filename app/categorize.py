"""A baseline, rule-based category classifier.

This is the "baseline rule" step described in docs/architecture.md's
machine-learning plan: a deterministic first pass based on keywords in the
merchant name, to be replaced or supplemented later by a model trained on
real category labels once enough of them exist. It never raises and never
calls out to anything external, so it stays fast and reproducible.
"""

import re

CATEGORIES: tuple[str, ...] = (
    "Food & Dining",
    "Transportation",
    "Housing & Utilities",
    "Shopping",
    "Entertainment",
    "Health & Fitness",
    "Other",
)

_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Food & Dining",
        (
            "restaurant", "cafe", "coffee", "starbucks", "mcdonald",
            "grocery", "doordash", "ubereats", "uber eats", "grubhub",
            "bar", "pizza", "deli", "bakery",
        ),
    ),
    (
        "Transportation",
        (
            "uber", "lyft", "gas", "shell", "chevron", "exxon", "parking",
            "transit", "airlines", "delta", "united airlines", "amtrak",
        ),
    ),
    (
        "Housing & Utilities",
        (
            "rent", "electric", "water bill", "internet", "comcast",
            "landlord", "mortgage", "utility", "utilities",
        ),
    ),
    (
        "Shopping",
        (
            "amazon", "target", "walmart", "store", "mall", "best buy",
            "clothing",
        ),
    ),
    (
        "Entertainment",
        (
            "netflix", "spotify", "movie", "theatre", "theater", "cinema",
            "concert", "steam", "hulu", "disney+",
        ),
    ),
    (
        "Health & Fitness",
        (
            "pharmacy", "cvs", "walgreens", "gym", "fitness", "doctor",
            "clinic", "hospital",
        ),
    ),
)


def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    """A regex that matches `keyword` only on word boundaries, so e.g. "gas"
    doesn't match inside "Las Vegas". A `\\b` is only added on a side whose
    edge character is alphanumeric -- "disney+" has no word character after
    the "+", so `\\b` would never match there and the keyword would never
    match at all."""
    escaped = re.escape(keyword)
    prefix = r"\b" if keyword[0].isalnum() else ""
    suffix = r"\b" if keyword[-1].isalnum() else ""
    return re.compile(prefix + escaped + suffix)


_COMPILED_KEYWORD_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (category, tuple(_keyword_pattern(keyword) for keyword in keywords))
    for category, keywords in _KEYWORD_RULES
)


def classify(merchant: str, description: str = "") -> str:
    """Guess a category for an expense from its merchant name and description.

    Matching is case-insensitive and keyword-boundary-aware over both fields
    together, so a keyword only matches a whole word (or word-like token),
    not an arbitrary substring -- "bar" matches "Corner Bar" but not "Barnes
    & Noble", and "gas" matches "Shell Gas Station" but not "Las Vegas".
    Falling back to "Other" is the expected outcome for a merchant the rules
    don't recognize -- this is a baseline, not a trained model, so it isn't
    meant to recognize everything.
    """
    haystack = f"{merchant} {description}".lower()
    for category, patterns in _COMPILED_KEYWORD_RULES:
        if any(pattern.search(haystack) for pattern in patterns):
            return category
    return "Other"

"""A baseline, rule-based category classifier.

This is the "baseline rule" step described in docs/architecture.md's
machine-learning plan: a deterministic first pass based on keywords in the
merchant name, to be replaced or supplemented later by a model trained on
real category labels once enough of them exist. It never raises and never
calls out to anything external, so it stays fast and reproducible.
"""

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


def classify(merchant: str, description: str = "") -> str:
    """Guess a category for an expense from its merchant name and description.

    Matching is a plain substring search, case-insensitive, over both
    fields together. Falling back to "Other" is the expected outcome for a
    merchant the rules don't recognize -- this is a baseline, not a trained
    model, so it isn't meant to recognize everything.
    """
    haystack = f"{merchant} {description}".lower()
    for category, keywords in _KEYWORD_RULES:
        if any(keyword in haystack for keyword in keywords):
            return category
    return "Other"

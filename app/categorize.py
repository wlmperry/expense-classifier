"""A baseline, rule-based category classifier.

This is the "baseline rule" step described in docs/architecture.md's
machine-learning plan: a deterministic first pass based on keywords in the
merchant name, to be replaced or supplemented later by a model trained on
real category labels once enough of them exist. It never raises and never
calls out to anything external, so it stays fast and reproducible.
"""

import re
from decimal import Decimal

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

    A thin wrapper around classify_with_confidence() for callers that only
    need the category. See that function for the matching rules.
    """
    return classify_with_confidence(merchant, description)[0]


def classify_with_confidence(merchant: str, description: str = "") -> tuple[str, Decimal]:
    """Guess a category for an expense, with a confidence score.

    Matching is case-insensitive and keyword-boundary-aware over both fields
    together, so a keyword only matches a whole word (or word-like token),
    not an arbitrary substring -- "bar" matches "Corner Bar" but not "Barnes
    & Noble", and "gas" matches "Shell Gas Station" but not "Las Vegas".
    Falling back to "Other" is the expected outcome for a merchant the rules
    don't recognize -- this is a baseline, not a trained model, so it isn't
    meant to recognize everything.

    A keyword match fully inside a longer match anywhere in the text is
    discarded before scoring -- e.g. "united airlines" also contains a
    standalone "airlines" match, and "uber eats" contains a standalone
    "uber" match (a different category's keyword entirely). Without this,
    a single, specific phrase would inflate its own category's hit count,
    or make an unrelated category look like it matched too.

    Confidence comes entirely from how many categories have a surviving
    match, and how many keywords within the chosen one do -- it is not a
    statistical probability, just a way to flag an ambiguous or unmatched
    guess as less trustworthy than a clean, unique match:
      - no category has a surviving match (falls back to "Other"): 0.2
      - exactly one category matches, on exactly one keyword: 0.75
      - exactly one category matches, on more than one keyword: 0.9
      - more than one category matches (ambiguous; the first one by rule
        order is returned, same as before this existed): 0.5
    """
    haystack = f"{merchant} {description}".lower()
    all_spans = [
        (match.start(), match.end(), category)
        for category, patterns in _COMPILED_KEYWORD_RULES
        for pattern in patterns
        for match in pattern.finditer(haystack)
    ]
    surviving_spans = [
        span
        for span in all_spans
        if not any(
            other[0] <= span[0] and span[1] <= other[1] and other != span
            for other in all_spans
        )
    ]

    hits_per_category: dict[str, int] = {}
    for _, _, category in surviving_spans:
        hits_per_category[category] = hits_per_category.get(category, 0) + 1

    matched = [
        (category, hits_per_category[category])
        for category, _ in _COMPILED_KEYWORD_RULES
        if category in hits_per_category
    ]

    if not matched:
        return "Other", Decimal("0.2")
    if len(matched) > 1:
        return matched[0][0], Decimal("0.5")
    category, hits = matched[0]
    return category, (Decimal("0.9") if hits > 1 else Decimal("0.75"))

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
    "Groceries",
    "Restaurants & Bars",
    "Coffee Shops",
    "Food Delivery",
    "Gas & Fuel",
    "Rideshare & Transit",
    "Travel",
    "Rent & Mortgage",
    "Utilities",
    "Online Shopping",
    "General Merchandise",
    "Electronics",
    "Clothing",
    "Streaming & Subscriptions",
    "Movies & Events",
    "Gaming",
    "Pharmacy",
    "Gym & Fitness",
    "Medical",
    "Other",
)

# Rule order is also the tie-break order: when keywords from more than one
# category match, classify_with_confidence() returns the first one listed
# here. That's why Groceries sits above General Merchandise ("Kroger Grocery
# Store" matches both "grocery" and "store", and Groceries is the better
# guess).
_KEYWORD_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Groceries",
        (
            "grocery", "groceries", "supermarket", "kroger", "whole foods",
            "trader joe", "aldi", "safeway",
        ),
    ),
    ("Restaurants & Bars", ("restaurant", "mcdonald", "bar", "pizza", "deli", "bakery")),
    ("Coffee Shops", ("cafe", "coffee", "starbucks")),
    ("Food Delivery", ("doordash", "ubereats", "uber eats", "grubhub", "instacart")),
    ("Gas & Fuel", ("gas", "fuel", "shell", "chevron", "exxon")),
    ("Rideshare & Transit", ("uber", "lyft", "taxi", "transit", "metro", "parking")),
    ("Travel", ("airlines", "delta", "united airlines", "amtrak", "hotel", "airbnb")),
    ("Rent & Mortgage", ("rent", "landlord", "mortgage")),
    ("Utilities", ("electric", "water bill", "internet", "comcast", "utility", "utilities")),
    ("Online Shopping", ("amazon", "ebay", "etsy")),
    ("General Merchandise", ("target", "walmart", "costco", "store", "mall")),
    ("Electronics", ("best buy", "apple store", "electronics")),
    ("Clothing", ("clothing", "apparel", "shoes", "nike")),
    ("Streaming & Subscriptions", ("netflix", "spotify", "hulu", "disney+")),
    ("Movies & Events", ("movie", "theatre", "theater", "cinema", "concert", "ticketmaster")),
    ("Gaming", ("steam", "xbox", "playstation", "nintendo")),
    ("Pharmacy", ("pharmacy", "cvs", "walgreens")),
    ("Gym & Fitness", ("gym", "fitness")),
    ("Medical", ("doctor", "clinic", "hospital", "dental")),
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
    match, and how many *distinct keywords* within the chosen one do --
    not how many times those keywords occur. "Starbucks" as both the
    merchant and the description is still one keyword match, not two; a
    repeated keyword (e.g. the same merchant name echoed into the
    description, common for Plaid imports) must not look more confident
    than it would with only one of those fields set. It is not a
    statistical probability, just a way to flag an ambiguous or unmatched
    guess as less trustworthy than a clean, unique match:
      - no category has a surviving match (falls back to "Other"): 0.2
      - exactly one category matches, on exactly one distinct keyword: 0.75
      - exactly one category matches, on more than one distinct keyword: 0.9
      - more than one category matches (ambiguous; the first one by rule
        order is returned, same as before this existed): 0.5
    """
    haystack = f"{merchant} {description}".lower()
    all_spans = [
        (match.start(), match.end(), category, pattern)
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

    keywords_per_category: dict[str, set[re.Pattern[str]]] = {}
    for _, _, category, pattern in surviving_spans:
        keywords_per_category.setdefault(category, set()).add(pattern)

    matched = [
        (category, len(keywords_per_category[category]))
        for category, _ in _COMPILED_KEYWORD_RULES
        if category in keywords_per_category
    ]

    if not matched:
        return "Other", Decimal("0.2")
    if len(matched) > 1:
        return matched[0][0], Decimal("0.5")
    category, hits = matched[0]
    return category, (Decimal("0.9") if hits > 1 else Decimal("0.75"))

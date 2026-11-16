"""A machine-learned category classifier (Issue #55).

It learns which bits of text go with which category from the labeled
examples in app/training_data.csv, so it can categorize merchants the keyword
rules in app/categorize.py have never heard of ("Dunkin", "Publix"). Those
rules still run first; this model is only asked when no rule matches (see
categorize() in app/categorize.py).

How it works, in two steps that scikit-learn chains into one Pipeline:

1. TfidfVectorizer turns text into numbers. It splits the text into short
   overlapping chunks of characters ("dun", "unk", "nki", ...) and gives each
   chunk a score: higher when the chunk appears in this text, lower when it
   appears in lots of training examples (so a common chunk like "the" counts
   for little). Character chunks, rather than whole words, let the model cope
   with abbreviations and store numbers ("PEETS 0451" still shares "pee",
   "eet" with "Peet's").
2. LogisticRegression learns a weight for every (chunk, category) pair from
   the training examples. To classify, it adds up the weights of the chunks
   in the text for each category and turns the totals into probabilities
   that sum to 1. The highest one is the prediction, and its probability is
   the confidence.

The model is trained in memory the first time it is needed (and on startup,
see app/main.py), from the CSV in the repo. Training on a few hundred rows
takes well under a second, so nothing is saved to disk: that avoids loading
a pickled model file, which can run arbitrary code, and keeps the model
exactly reproducible from the CSV.
"""

import csv
import re
from decimal import Decimal
from functools import cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline

TRAINING_DATA_PATH = Path(__file__).with_name("training_data.csv")


def normalize(merchant: str, description: str = "") -> str:
    """The text the model sees: merchant and description together,
    lowercased, with digits and symbols like "#" removed. Store numbers and
    dates ("#3321", "0412") vary from one transaction to the next and say
    nothing about the category, so keeping them would only add noise."""
    text = f"{merchant} {description}".lower()
    text = re.sub(r"[^a-z&+.' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_training_data(path: Path = TRAINING_DATA_PATH) -> tuple[list[str], list[str]]:
    """The training examples as (texts, categories), in file order."""
    texts: list[str] = []
    categories: list[str] = []
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            texts.append(normalize(row["merchant"], row["description"]))
            categories.append(row["category"])
    return texts, categories


def build_model() -> Pipeline:
    """An untrained model. Every setting here is fixed, so training on the
    same data always produces the same model."""
    return make_pipeline(
        # char_wb: character chunks that don't cross word boundaries.
        # 2 to 5 characters long. sublinear_tf dampens a chunk repeated many
        # times (e.g. when the description repeats the merchant name).
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True),
        # C controls how closely the model fits the training examples:
        # higher fits them more tightly. max_iter just gives the solver
        # enough steps to finish.
        LogisticRegression(C=10, max_iter=2000),
    )


def train_model(texts: list[str], categories: list[str]) -> Pipeline:
    model = build_model()
    model.fit(texts, categories)
    return model


@cache
def get_model() -> Pipeline:
    """The model trained on app/training_data.csv. Trained once per process
    and reused (that's what @cache does)."""
    return train_model(*load_training_data())


def predict(merchant: str, description: str = "") -> tuple[str, Decimal]:
    """The model's best category for this expense and its probability,
    rounded to two decimal places to fit the confidence column."""
    model = get_model()
    probabilities = model.predict_proba([normalize(merchant, description)])[0]
    best = probabilities.argmax()
    confidence = Decimal(str(round(float(probabilities[best]), 2)))
    return str(model.classes_[best]), confidence

from datetime import datetime

import numpy as np

from app.models.transaction import Transaction
from app.services.categorizer import Categorizer


def test_merchant_categorization():
    categorizer = Categorizer()
    swiggy = categorizer.classify(Transaction(date=datetime.now(), description="UPI-SWIGGY", amount=450))
    uber = categorizer.classify(Transaction(date=datetime.now(), description="UBER INDIA", amount=220))
    amazon = categorizer.classify(Transaction(date=datetime.now(), description="AMAZON INDIA", amount=100))
    assert swiggy == {"category": "Food", "classification_method": "merchant_rule", "confidence": 0.99}
    assert uber["category"] == "Transport"
    assert uber["classification_method"] == "merchant_rule"
    assert amazon["category"] == "Shopping"
    assert amazon["classification_method"] == "merchant_rule"


def test_unknown_is_other():
    transaction = Transaction(date=datetime.now(), description="MYSTERY PAYMENT XYZ", amount=100)
    result = Categorizer().classify(transaction)
    assert result["category"] == "Other"
    assert result["classification_method"] == "fallback"


class FakeEmbeddingModel:
    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            text = text.lower()
            if any(word in text for word in ("food", "cafe", "restaurant", "swiggy", "zomato", "bakery")):
                vectors.append([1.0, 0.0, 0.0])
            elif any(word in text for word in ("uber", "ola", "taxi", "metro", "train", "transport")):
                vectors.append([0.0, 1.0, 0.0])
            elif any(word in text for word in ("amazon", "flipkart", "shopping", "clothing", "retail")):
                vectors.append([0.0, 0.0, 1.0])
            else:
                vectors.append([0.0, 0.0, 0.0])
        return np.asarray(vectors)


def test_unknown_cafe_uses_embedding_similarity():
    transaction = Transaction(date=datetime.now(), description="UNKNOWN CAFE KOCHI", amount=540)
    result = Categorizer(embedding_model=FakeEmbeddingModel()).classify(transaction)
    assert result["category"] == "Food"
    assert result["classification_method"] == "embedding_similarity"
    assert result["confidence"] == 1.0


def test_unknown_unrelated_text_falls_below_threshold():
    transaction = Transaction(date=datetime.now(), description="ZXQ-1847-UNRELATED", amount=100)
    result = Categorizer(embedding_model=FakeEmbeddingModel()).classify(transaction)
    assert result["category"] == "Other"
    assert result["classification_method"] == "fallback"
    assert result["confidence"] == 0.0

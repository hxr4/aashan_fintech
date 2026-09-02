import os
import re
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from app.models.transaction import Transaction


CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Entertainment", "Healthcare", "Education", "Salary", "Other"]
MERCHANT_CATEGORIES = {
    "swiggy": "Food", "zomato": "Food", "dominos": "Food", "blinkit": "Food",
    "uber": "Transport", "ola": "Transport", "rapido": "Transport", "metro": "Transport",
    "amazon": "Shopping", "flipkart": "Shopping", "myntra": "Shopping", "meesho": "Shopping",
    "netflix": "Entertainment", "spotify": "Entertainment", "prime video": "Entertainment",
    "jio": "Bills", "airtel": "Bills", "vi recharge": "Bills", "electricity": "Bills", "broadband": "Bills",
    "apollo": "Healthcare", "pharmeasy": "Healthcare", "hospital": "Healthcare", "doctor": "Healthcare",
    "school": "Education", "course": "Education", "udemy": "Education", "college": "Education",
    "salary": "Salary", "payroll": "Salary", "stipend": "Salary",
}
KEYWORD_CATEGORIES = {
    "food": "Food", "restaurant": "Food", "grocery": "Food",
    "fuel": "Transport", "petrol": "Transport", "parking": "Transport", "travel": "Transport", "flight": "Transport",
    "shopping": "Shopping", "purchase": "Shopping", "emi": "Bills", "recharge": "Bills",
    "insurance": "Bills", "movie": "Entertainment", "games": "Entertainment", "medicine": "Healthcare",
    "tuition": "Education", "fees": "Education",
}

CATEGORY_EXEMPLARS = {
    "Food": ["restaurant", "cafe", "food delivery", "grocery", "fast food", "bakery", "swiggy", "zomato"],
    "Transport": ["taxi", "cab", "ride", "uber", "ola", "metro", "bus", "train", "fuel"],
    "Shopping": ["online shopping", "clothing", "electronics", "amazon", "flipkart", "retail store"],
    "Bills": ["electricity bill", "internet bill", "mobile recharge", "phone bill", "utility bill", "insurance payment"],
    "Entertainment": ["movie", "cinema", "streaming subscription", "netflix", "spotify", "gaming"],
    "Education": ["college fee", "tuition", "course", "education", "university", "books"],
    "Healthcare": ["pharmacy", "hospital", "doctor", "medical", "medicine", "healthcare"],
}

DEFAULT_SIMILARITY_THRESHOLD = 0.55
_EMBEDDING_MODEL = None
_EXEMPLAR_EMBEDDINGS = None
_EMBEDDING_UNAVAILABLE = False


class Categorizer:
    def __init__(self, embedding_model: Any = None, similarity_threshold: Optional[float] = None) -> None:
        self._provided_model = embedding_model
        self._provided_exemplar_embeddings = None
        configured_threshold = os.getenv("AASHAN_EMBEDDING_THRESHOLD", str(DEFAULT_SIMILARITY_THRESHOLD))
        self.similarity_threshold = float(similarity_threshold if similarity_threshold is not None else configured_threshold)

    def _load_model(self) -> Any:
        global _EMBEDDING_MODEL, _EMBEDDING_UNAVAILABLE
        if self._provided_model is not None:
            return self._provided_model
        if os.getenv("AASHAN_ENABLE_EMBEDDINGS", "true").lower() not in {"1", "true", "yes"}:
            return None
        if _EMBEDDING_MODEL is not None or _EMBEDDING_UNAVAILABLE:
            return _EMBEDDING_MODEL
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            _EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            return _EMBEDDING_MODEL
        except Exception:
            # The application remains usable when model weights are unavailable.
            _EMBEDDING_UNAVAILABLE = True
            return None

    def _exemplar_embeddings(self, model: Any) -> Dict[str, np.ndarray]:
        global _EXEMPLAR_EMBEDDINGS
        if self._provided_model is None and _EXEMPLAR_EMBEDDINGS is not None:
            return _EXEMPLAR_EMBEDDINGS
        if self._provided_model is not None and self._provided_exemplar_embeddings is not None:
            return self._provided_exemplar_embeddings
        categories = list(CATEGORY_EXEMPLARS.keys())
        phrases = [phrase for category in categories for phrase in CATEGORY_EXEMPLARS[category]]
        vectors = np.asarray(model.encode(phrases, convert_to_numpy=True, normalize_embeddings=False))
        result: Dict[str, np.ndarray] = {}
        cursor = 0
        for category in categories:
            size = len(CATEGORY_EXEMPLARS[category])
            result[category] = vectors[cursor:cursor + size]
            cursor += size
        if self._provided_model is None:
            _EXEMPLAR_EMBEDDINGS = result
        else:
            self._provided_exemplar_embeddings = result
        return result

    @staticmethod
    def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        if denominator == 0:
            return 0.0
        return float(np.dot(left, right) / denominator)

    def _embedding_classification(self, text: str) -> Optional[Dict[str, Any]]:
        model = self._load_model()
        if model is None:
            return None
        try:
            query = np.asarray(model.encode([text], convert_to_numpy=True, normalize_embeddings=False))[0]
            exemplar_embeddings = self._exemplar_embeddings(model)
            scores = {
                category: max(self._cosine_similarity(query, exemplar) for exemplar in vectors)
                for category, vectors in exemplar_embeddings.items()
            }
            category, score = max(scores.items(), key=lambda item: item[1])
            score = round(float(score), 4)
            if score < self.similarity_threshold:
                return {"category": "Other", "classification_method": "fallback", "confidence": score}
            return {"category": category, "classification_method": "embedding_similarity", "confidence": score}
        except Exception:
            return None

    def classify(self, transaction: Transaction) -> Dict[str, Any]:
        text = " ".join(filter(None, [transaction.merchant, transaction.description])).lower()
        for merchant, category in MERCHANT_CATEGORIES.items():
            if re.search(r"\b" + re.escape(merchant) + r"\b", text):
                return {"category": category, "classification_method": "merchant_rule", "confidence": 0.99}
        for keyword, category in KEYWORD_CATEGORIES.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", text):
                return {"category": category, "classification_method": "keyword_rule", "confidence": 0.95}
        embedding_result = self._embedding_classification(text)
        return embedding_result or {"category": "Other", "classification_method": "fallback", "confidence": 0.0}

    def categorize(self, transaction: Transaction) -> str:
        return self.classify(transaction)["category"]

    def categorize_transactions(self, transactions: Iterable[Transaction]) -> List[Transaction]:
        result = []
        for transaction in transactions:
            classification = self.classify(transaction)
            transaction.category = classification["category"]
            transaction.classification_method = classification["classification_method"]
            transaction.confidence = classification["confidence"]
            result.append(transaction)
        return result


def categorize_transactions(transactions: Iterable[Transaction]) -> List[Transaction]:
    return Categorizer().categorize_transactions(transactions)

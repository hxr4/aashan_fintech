from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["CSV", "PDF", "SMS", "SETU", "MANUAL"]
Direction = Literal["CREDIT", "DEBIT", "TRANSFER"]
TransactionLifecycle = Literal[
    "RECEIVED",
    "EXTRACTED",
    "NORMALIZED",
    "CLASSIFIED",
    "PENDING_REVIEW",
    "CONFIRMED",
    "REJECTED",
    "DUPLICATE",
    "FAILED",
    "DELETED",
]
ClassificationStatus = Literal["AUTO_CLASSIFIED", "USER_CONFIRMED", "USER_CORRECTED", "AMBIGUOUS"]
BudgetStatus = Literal["UNDECIDED", "INCLUDED", "EXCLUDED"]
TransferStatus = Literal["NOT_TRANSFER", "POSSIBLE", "CONFIRMED", "REJECTED"]
DuplicateStatus = Literal["NOT_DUPLICATE", "POSSIBLE_DUPLICATE", "CONFIRMED_DUPLICATE"]


class NormalizedTransactionInput(BaseModel):
    """Source-neutral financial record passed between adapters and ingestion."""

    transaction_at: datetime
    value_date: Optional[datetime] = None
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    direction: Direction = "DEBIT"
    transaction_type: Direction = "DEBIT"
    description: str = ""
    mode: str = "UNKNOWN"
    merchant_candidate: Optional[str] = None
    merchant_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    category_candidate: Optional[str] = None
    source_type: SourceType
    source_record_id: Optional[str] = None
    external_id: Optional[str] = None
    account_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TransactionReviewRequest(BaseModel):
    # Unknown keys are rejected rather than ignored, so a client cannot smuggle
    # a field in and have a future version silently start honouring it.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: Literal[
        "APPROVE",
        "REJECT",
        "EDIT",
        "CORRECT_CATEGORY",
        "CORRECT_MERCHANT",
        "INCLUDE_IN_BUDGET",
        "EXCLUDE_FROM_BUDGET",
        "MARK_TRANSFER",
        "MARK_DUPLICATE",
    ]
    category: Optional[str] = Field(default=None, max_length=100)
    merchant: Optional[str] = Field(default=None, max_length=200)
    # Correcting a misparsed amount is legitimate, but it is honoured only for
    # an explicit EDIT and is always written to the review audit log.
    amount: Optional[float] = Field(default=None, gt=0, le=1_000_000_000)
    description: Optional[str] = Field(default=None, max_length=500)


class MerchantRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    merchant_pattern: str = Field(min_length=1, max_length=200)
    category: Optional[str] = Field(default=None, max_length=100)


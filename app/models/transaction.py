from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    date: datetime
    description: str
    amount: float = Field(gt=0)
    mode: str = "UNKNOWN"
    transaction_type: str = "DEBIT"
    merchant: Optional[str] = None
    category: Optional[str] = None
    classification_method: Optional[str] = None
    confidence: Optional[float] = None
    user_id: Optional[str] = None
    account_id: Optional[str] = None
    source: Optional[str] = None
    import_id: Optional[str] = None
    source_record_id: Optional[str] = None
    external_id: Optional[str] = None
    currency: str = "INR"
    status: str = "CONFIRMED"
    classification_status: str = "CLASSIFIED"
    budget_inclusion: str = "UNDECIDED"
    is_transfer: bool = False
    transaction_at: Optional[datetime] = None
    value_date: Optional[datetime] = None
    source_type: Optional[str] = None
    merchant_candidate: Optional[str] = None
    merchant_confidence: Optional[float] = None
    transaction_status: str = "CONFIRMED"
    budget_status: str = "UNDECIDED"
    transfer_status: str = "NOT_TRANSFER"
    duplicate_status: str = "NOT_DUPLICATE"


class TransactionInput(BaseModel):
    date: str
    description: str
    amount: float
    mode: str = "UNKNOWN"
    transaction_type: str = "DEBIT"

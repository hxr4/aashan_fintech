from typing import Any, Dict, Optional

from app.auth import LOCAL_USER_ID
from app.config import settings
from app.database.connection import get_sqlite_connection, run_migrations, sqlite_db_path
from app.database.repository import get_repository
from app.models.ingestion import NormalizedTransactionInput


DB_PATH = sqlite_db_path() if settings.database_url.startswith("sqlite:///") else ""


def get_connection():
    return get_sqlite_connection()


def init_db() -> None:
    run_migrations()


def save_aggregate(payload: Dict[str, Any], user_id: str = LOCAL_USER_ID, source: str = "PIPELINE", import_id: Optional[str] = None) -> None:
    get_repository().save_aggregate(payload, user_id, source, import_id)


def latest_aggregate(user_id: str = LOCAL_USER_ID) -> Dict[str, Any]:
    return get_repository().latest_aggregate(user_id)


def save_budgets(budgets: Dict[str, float], user_id: str = LOCAL_USER_ID) -> None:
    get_repository().save_budgets(budgets, user_id)


def get_budgets(user_id: str = LOCAL_USER_ID) -> Dict[str, float]:
    return get_repository().get_budgets(user_id)


def save_aa_consent_context(consent_id: str, data_range_from: str, data_range_to: str, auto_fetch: bool, user_id: str = LOCAL_USER_ID, purpose: Optional[Dict[str, Any]] = None) -> None:
    get_repository().save_aa_consent_context(consent_id, data_range_from, data_range_to, auto_fetch, user_id, purpose)


def get_aa_consent_context(consent_id: str) -> Optional[Dict[str, Any]]:
    return get_repository().get_aa_consent_context(consent_id)


def update_aa_consent_status(consent_id: str, status: str, user_id: Optional[str] = None) -> None:
    get_repository().update_aa_consent_status(consent_id, status, user_id)


def mark_aa_webhook_event(event_key: str, event_type: str, consent_id: Optional[str], session_id: Optional[str]) -> bool:
    return get_repository().mark_aa_webhook_event(event_key, event_type, consent_id, session_id)


def aa_webhook_event_processed(event_key: str) -> bool:
    return get_repository().aa_webhook_event_processed(event_key)


def aa_session_processed(session_id: str) -> bool:
    return get_repository().aa_session_processed(session_id)


def mark_aa_session_processed(session_id: str) -> None:
    get_repository().mark_aa_session_processed(session_id)


def privacy_database_status(user_id: str = LOCAL_USER_ID) -> Dict[str, Any]:
    return get_repository().privacy_database_status(user_id)


def create_import(user_id: str, source: str, filename: Optional[str] = None, account_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    return get_repository().create_import(user_id, source, filename, account_id, idempotency_key)


def complete_import(import_id: str, user_id: str, status: str, row_count: int = 0, error_category: Optional[str] = None, error_message: Optional[str] = None) -> None:
    get_repository().complete_import(import_id, user_id, status, row_count, error_category, error_message)


def create_processing_job(user_id: str, import_id: str, job_type: str) -> str:
    return get_repository().create_processing_job(user_id, import_id, job_type)


def update_processing_checkpoint(job_id: str, user_id: str, checkpoint: str, status: Optional[str] = None, progress: Optional[Dict[str, Any]] = None) -> None:
    get_repository().update_processing_checkpoint(job_id, user_id, checkpoint, status, progress)


def complete_processing_job(job_id: str, user_id: str, status: str = "COMPLETED", error_category: Optional[str] = None, error_message: Optional[str] = None) -> None:
    get_repository().complete_processing_job(job_id, user_id, status, error_category, error_message)


def create_candidate(user_id: str, import_id: str, item: NormalizedTransactionInput, *args: Any, **kwargs: Any) -> str:
    return get_repository().create_candidate(user_id, import_id, item, *args, **kwargs)


def get_candidate(user_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
    return get_repository().get_candidate(user_id, candidate_id)


def list_candidates(user_id: str, review_status: Optional[str] = None) -> list[Dict[str, Any]]:
    return get_repository().list_candidates(user_id, review_status)


def update_candidate(user_id: str, candidate_id: str, review_status: str, transaction_status: str, classification_status: Optional[str] = None) -> bool:
    return get_repository().update_candidate(user_id, candidate_id, review_status, transaction_status, classification_status)


def create_transaction(user_id: str, import_id: str, candidate_id: str, item: NormalizedTransactionInput, *args: Any, **kwargs: Any) -> Dict[str, Any]:
    return get_repository().create_transaction(user_id, import_id, candidate_id, item, *args, **kwargs)


def get_transaction(user_id: str, transaction_id: str) -> Optional[Dict[str, Any]]:
    return get_repository().get_transaction(user_id, transaction_id)


def list_transactions(user_id: str, transaction_status: Optional[str] = "CONFIRMED") -> list[Dict[str, Any]]:
    return get_repository().list_transactions(user_id, transaction_status)


def update_transaction(user_id: str, transaction_id: str, updates: Dict[str, Any]) -> bool:
    return get_repository().update_transaction(user_id, transaction_id, updates)


def list_observations(user_id: str, transaction_id: str) -> list[Dict[str, Any]]:
    return get_repository().list_observations(user_id, transaction_id)


def list_review_queue(user_id: str) -> list[Dict[str, Any]]:
    return get_repository().list_review_queue(user_id)


def record_coverage(user_id: str, source: str, covered_from: str, covered_to: str, account_id: Optional[str] = None) -> None:
    get_repository().record_coverage(user_id, source, covered_from, covered_to, account_id)


def list_coverage(user_id: str) -> list[Dict[str, Any]]:
    return get_repository().list_coverage(user_id)


def purge_user(user_id: str) -> Dict[str, int]:
    return get_repository().purge_user(user_id)


def get_processing_job(user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    return get_repository().get_processing_job(user_id, job_id)


def list_processing_jobs(user_id: str) -> list[Dict[str, Any]]:
    return get_repository().list_processing_jobs(user_id)


def record_privacy_event(user_id: str, event_type: str, metadata: Dict[str, Any]) -> None:
    get_repository().record_privacy_event(user_id, event_type, metadata)


def create_review(user_id: str, candidate_id: Optional[str], transaction_id: Optional[str], action: str, changes: Dict[str, Any]) -> str:
    return get_repository().create_review(user_id, candidate_id, transaction_id, action, changes)


def create_merchant_rule(user_id: str, merchant_pattern: str, category: Optional[str]) -> str:
    return get_repository().create_merchant_rule(user_id, merchant_pattern, category)


def list_merchant_rules(user_id: str) -> list[Dict[str, Any]]:
    return get_repository().list_merchant_rules(user_id)


def list_imports(user_id: str) -> list[Dict[str, Any]]:
    return get_repository().list_imports(user_id)


def get_import(user_id: str, import_id: str) -> Optional[Dict[str, Any]]:
    return get_repository().get_import(user_id, import_id)

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import AuthenticatedUser, get_current_user
from app.database import db
from app.models.ingestion import MerchantRuleRequest, TransactionReviewRequest
from app.services.review import review_candidate, review_transaction


router = APIRouter(tags=["financial records"])


@router.get("/api/imports", summary="List owned imports")
def list_owned_imports(user: AuthenticatedUser = Depends(get_current_user)):
    return {"imports": db.list_imports(user.user_id)}


@router.get("/api/imports/{import_id}", summary="Get one owned import")
def get_owned_import(import_id: str, user: AuthenticatedUser = Depends(get_current_user)):
    record = db.get_import(user.user_id, import_id)
    if not record:
        raise HTTPException(status_code=404, detail="Import not found")
    return record


@router.get("/api/transaction-candidates", summary="List owned transaction candidates")
def list_owned_candidates(status: Optional[str] = Query(default=None), user: AuthenticatedUser = Depends(get_current_user)):
    return {"candidates": db.list_candidates(user.user_id, status)}


@router.post("/api/transaction-candidates/{candidate_id}/review", summary="Review one owned candidate")
def review_owned_candidate(candidate_id: str, request: TransactionReviewRequest, user: AuthenticatedUser = Depends(get_current_user)):
    result = review_candidate(user.user_id, candidate_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction candidate not found")
    return result


@router.get("/api/transactions", summary="List owned canonical transactions")
def list_owned_transactions(status: Optional[str] = Query(default="CONFIRMED"), user: AuthenticatedUser = Depends(get_current_user)):
    return {"transactions": db.list_transactions(user.user_id, status)}


@router.post("/api/transactions/{transaction_id}/review", summary="Review one owned transaction")
def review_owned_transaction(transaction_id: str, request: TransactionReviewRequest, user: AuthenticatedUser = Depends(get_current_user)):
    result = review_transaction(user.user_id, transaction_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.post("/api/merchant-rules", summary="Create a user-specific merchant rule")
def create_owned_merchant_rule(request: MerchantRuleRequest, user: AuthenticatedUser = Depends(get_current_user)):
    rule_id = db.create_merchant_rule(user.user_id, request.merchant_pattern, request.category)
    return {"id": rule_id, "user_id": user.user_id, "merchant_pattern": request.merchant_pattern, "category": request.category}

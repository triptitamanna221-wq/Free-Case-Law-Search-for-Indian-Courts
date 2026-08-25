from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import Judgment
from app.schemas.judgment import JudgmentDetail

router = APIRouter(tags=["judgments"])


@router.get("/judgments/{judgment_id}", response_model=JudgmentDetail)
def get_judgment(judgment_id: int, db: Session = Depends(get_db)) -> Judgment:
    judgment = db.scalar(select(Judgment).where(Judgment.id == judgment_id))
    if judgment is None:
        raise HTTPException(status_code=404, detail="Judgment not found")
    return judgment

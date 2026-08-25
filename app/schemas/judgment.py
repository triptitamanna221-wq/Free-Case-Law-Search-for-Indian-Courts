from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class JudgmentDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    court: str | None
    case_type: str | None
    decision_date: date | None
    judges: list[str] | None
    petitioner: str | None
    respondent: str | None
    raw_text: str
    source_dataset: str
    source_url: str | None
    created_at: datetime

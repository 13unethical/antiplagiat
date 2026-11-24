import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MatchOut(BaseModel):
    id: uuid.UUID
    start_char: int
    end_char: int
    matched_text: str
    source_title: str
    source_url: Optional[str]
    source_lang: str
    match_kind: str
    score: float
    created_at: datetime

    model_config = {"from_attributes": True}

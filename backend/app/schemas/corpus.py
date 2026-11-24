import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl


class CorpusDocumentIn(BaseModel):
    title: str
    content: str
    url: Optional[str] = None
    language: str = "ru"
    source_type: str = "web"


class CorpusDocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    url: Optional[str]
    language: str
    source_type: str
    word_count: int
    created_at: datetime

    model_config = {"from_attributes": True}

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.schemas.match import MatchOut


class CheckOut(BaseModel):
    id: uuid.UUID
    filename: str
    file_size: int
    status: str
    work_title: Optional[str] = None
    student_name: Optional[str] = None
    student_id: Optional[str] = None
    group_name: Optional[str] = None
    word_count: Optional[int]
    language: Optional[str]
    similarity_percent: Optional[float]
    similarity_sources_count: Optional[int]
    ai_percent: Optional[float] = None
    ai_model_version: Optional[str] = None
    mt_flag: Optional[bool] = None
    mt_percent: Optional[float] = None
    stylometry_score: Optional[float] = None
    save_to_repository: bool = False
    excluded_sources: list = []
    exclude_quotes: bool = False
    exclude_bibliography: bool = True
    min_match_words: int = 8
    flag_count: int = 0
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class FlagOut(BaseModel):
    id: uuid.UUID
    type: str
    severity: str
    count: int
    details: dict

    model_config = {"from_attributes": True}


class MTSegmentOut(BaseModel):
    id: uuid.UUID
    start_char: int
    end_char: int
    probability: float
    mt_kind: str

    model_config = {"from_attributes": True}


class CheckDetailOut(CheckOut):
    flags: list[FlagOut] = []
    matches: list[MatchOut] = []
    mt_segments: list[MTSegmentOut] = []
    text_preview: Optional[str] = None
    full_text: Optional[str] = None
    ocr_used: bool = False

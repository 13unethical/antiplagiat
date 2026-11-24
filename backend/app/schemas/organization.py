import uuid
from datetime import date
from typing import Optional
from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    seats_limit: int = 10
    monthly_quota: int = 1000
    plan: str = "standard"
    valid_until: Optional[date] = None


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    seats_limit: int
    monthly_quota: int
    plan: str
    valid_until: Optional[date]
    default_exclude_quotes: bool = True
    default_exclude_bibliography: bool = True
    default_save_to_repository: bool = False
    default_min_match_words: int = 8
    require_student_name: bool = False
    require_group: bool = False
    report_footer: str = ""

    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    seats_limit: Optional[int] = None
    monthly_quota: Optional[int] = None
    plan: Optional[str] = None
    valid_until: Optional[date] = None
    default_exclude_quotes: Optional[bool] = None
    default_exclude_bibliography: Optional[bool] = None
    default_save_to_repository: Optional[bool] = None
    default_min_match_words: Optional[int] = None
    require_student_name: Optional[bool] = None
    require_group: Optional[bool] = None
    report_footer: Optional[str] = None

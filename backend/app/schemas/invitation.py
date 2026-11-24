import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class InvitationCreate(BaseModel):
    email: EmailStr
    # superadmin указывает role и org_id; school_admin всегда создаёт teacher
    role: str
    org_id: Optional[uuid.UUID] = None


class InvitationOut(BaseModel):
    id: uuid.UUID
    token: str
    email: str
    role: str
    status: str
    expires_at: datetime
    org_id: uuid.UUID

    model_config = {"from_attributes": True}


class AcceptInvitation(BaseModel):
    full_name: str
    password: str

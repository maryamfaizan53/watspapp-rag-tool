from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdminRole(str, Enum):
    super_admin = "super_admin"
    tenant_admin = "tenant_admin"


class AdminUserBase(BaseModel):
    email: str
    role: AdminRole = AdminRole.super_admin
    tenant_id: Optional[UUID] = None  # null for super_admin
    is_active: bool = True


class AdminUserCreate(AdminUserBase):
    hashed_password: str


class AdminUserSchema(AdminUserBase):
    id: UUID
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

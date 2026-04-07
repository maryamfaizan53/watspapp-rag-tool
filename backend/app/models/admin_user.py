from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field


class AdminRole(str, Enum):
    super_admin = "super_admin"
    tenant_admin = "tenant_admin"


class AdminUser(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    email: str
    hashed_password: str
    role: AdminRole = AdminRole.super_admin
    tenant_id: Optional[str] = None  # null for super_admin
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

    def to_doc(self) -> dict:
        data = self.model_dump(by_alias=False, exclude={"id"})
        if self.id:
            data["_id"] = ObjectId(self.id)
        if self.tenant_id:
            data["tenant_id"] = ObjectId(self.tenant_id)
        return data

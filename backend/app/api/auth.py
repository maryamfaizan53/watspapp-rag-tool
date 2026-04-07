from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.config import settings
from app.db.mongo import get_db
from app.models.admin_user import AdminUser

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

ALGORITHM = "HS256"


# ── Schemas ──────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ── Helpers ──────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AdminUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        admin_id: str = payload.get("sub")
        if admin_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    db = get_db()
    doc = await db.admin_users.find_one({"_id": ObjectId(admin_id), "is_active": True})
    if not doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    doc["_id"] = str(doc["_id"])
    return AdminUser(**doc)


# ── Routes ────────────────────────────────────────────────────────────


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    db = get_db()
    doc = await db.admin_users.find_one({"email": body.email.lower(), "is_active": True})
    if not doc or not verify_password(body.password, doc["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Update last_login_at
    await db.admin_users.update_one(
        {"_id": doc["_id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc)}},
    )

    token = create_access_token(str(doc["_id"]))
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post("/logout", status_code=204)
async def logout(
    _: AdminUser = Depends(get_current_admin),
) -> None:
    # Stateless JWT — client discards token
    return None

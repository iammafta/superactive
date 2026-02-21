"""
Superactive -- Auth Routes

POST /api/auth/register  - Create tenant + first admin user, returns JWT
POST /api/auth/login     - Validate credentials, returns JWT
GET  /api/auth/me        - Get current user info (requires auth)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth import (
    hash_password,
    verify_password,
    create_token,
    get_current_user,
    UserContext,
)
from db import db_create_tenant, db_create_user, db_get_user_by_email, db_get_tenant

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


# ── Request / Response Models ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    business_name: str = "My Business"


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


# ── Register ──────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
@limiter.limit("10/hour")
async def register(request: Request, req: RegisterRequest):
    """Create a new tenant and admin user."""
    # Check if email already exists
    existing = await db_get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    if len(req.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")

    # Create tenant
    tenant = await db_create_tenant(name=req.business_name, email=req.email)

    # Create admin user
    pw_hash = hash_password(req.password)
    user = await db_create_user(
        email=req.email,
        password_hash=pw_hash,
        tenant_id=tenant["id"],
        role="admin",
    )

    # Generate JWT
    token = create_token(
        user_id=user["id"],
        tenant_id=tenant["id"],
        email=user["email"],
        role=user["role"],
    )

    logger.info(f"🆕 New tenant registered: {req.business_name} ({req.email})")

    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "tenant_id": tenant["id"],
            "role": user["role"],
            "tenant_name": tenant["name"],
        },
    )


# ── Login ─────────────────────────────────────────────────────────────

@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest):
    """Authenticate with email + password, returns JWT."""
    user = await db_get_user_by_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        email=user["email"],
        role=user.get("role", "admin"),
    )

    logger.info(f"🔑 User logged in: {req.email}")

    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "tenant_id": user["tenant_id"],
            "role": user.get("role", "admin"),
            "tenant_name": user.get("tenant_name", ""),
        },
    )


# ── Me (Current User Info) ───────────────────────────────────────────

@router.get("/me")
async def me(user: UserContext = Depends(get_current_user)):
    """Return the current user's info (requires valid JWT)."""
    tenant = await db_get_tenant(user.tenant_id)
    return {
        "id": user.user_id,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "role": user.role,
        "tenant_name": tenant["name"] if tenant else "",
        "plan": tenant.get("plan", "starter") if tenant else "starter",
    }

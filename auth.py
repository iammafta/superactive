"""
Superactive -- Authentication

JWT token creation/verification and password hashing.
Uses stdlib hashlib (PBKDF2) for passwords and PyJWT for tokens.
Zero extra dependencies beyond what's already installed.

FastAPI dependency `get_current_user` extracts the tenant context
from the Authorization header on every protected endpoint.
"""

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Header, HTTPException
from loguru import logger


# ── Config ────────────────────────────────────────────────────────────

# JWT_SECRET is loaded from env. If missing, a random one is generated
# (fine for dev — tokens won't survive server restarts).
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = hashlib.sha256(os.urandom(64)).hexdigest()
    logger.warning("⚠️  No JWT_SECRET in .env — using random secret (tokens reset on restart)")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 72  # 3 days


# ── Password Hashing (PBKDF2-SHA256, OWASP recommended) ──────────────

_PBKDF2_ITERATIONS = 600_000  # OWASP 2024 recommendation for SHA-256


def hash_password(password: str) -> str:
    """Hash a password with a random salt. Returns 'salt_hex$hash_hex'."""
    salt = os.urandom(32)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${h.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt_hex, hash_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
        return actual == expected
    except (ValueError, AttributeError):
        return False


# ── JWT Tokens ────────────────────────────────────────────────────────

def create_token(user_id: str, tenant_id: str, email: str, role: str = "admin") -> str:
    """Create a signed JWT with user context."""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT. Returns payload or None."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── FastAPI Dependency ────────────────────────────────────────────────

@dataclass
class UserContext:
    """Injected into every protected endpoint via Depends(get_current_user)."""
    user_id: str
    tenant_id: str
    email: str
    role: str


async def get_current_user(authorization: str = Header(None)) -> UserContext:
    """
    Extract and verify the Bearer token from the Authorization header.
    Returns a UserContext on success, raises 401 on failure.

    Usage:
        @router.get("/api/something")
        async def something(user: UserContext = Depends(get_current_user)):
            # user.tenant_id is guaranteed to be valid
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # Accept "Bearer <token>" or raw token
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1]
    elif len(parts) == 1:
        token = parts[0]
    else:
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return UserContext(
        user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
        email=payload["email"],
        role=payload.get("role", "admin"),
    )

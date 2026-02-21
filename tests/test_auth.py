"""
Tests for auth.py — password hashing, JWT tokens, and user context extraction.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import hash_password, verify_password, create_token, decode_token


class TestPasswordHashing:
    """Tests for PBKDF2 password hashing."""

    def test_hash_password_returns_string(self):
        result = hash_password("test-password-12chars")
        assert isinstance(result, str)
        assert len(result) > 50

    def test_hash_password_format(self):
        """Hash format is 'salt_hex$hash_hex' (2 parts)."""
        result = hash_password("another-password-ok")
        parts = result.split("$")
        assert len(parts) == 2
        # Both should be valid hex
        assert all(c in "0123456789abcdef" for c in parts[0])
        assert all(c in "0123456789abcdef" for c in parts[1])

    def test_hash_password_unique_salts(self):
        h1 = hash_password("same-password-xxxxx")
        h2 = hash_password("same-password-xxxxx")
        assert h1 != h2  # Different salts each time

    def test_verify_password_correct(self):
        pw = "correct-horse-battery"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_password_wrong(self):
        hashed = hash_password("right-password!")
        assert verify_password("wrong-password!", hashed) is False

    def test_verify_password_empty(self):
        hashed = hash_password("some-password!!")
        assert verify_password("", hashed) is False


class TestJWTTokens:
    """Tests for JWT token creation and decoding."""

    def test_create_token_returns_string(self):
        token = create_token(
            user_id="u1", tenant_id="t1", email="test@test.com", role="admin"
        )
        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_token_roundtrip(self):
        """JWT payload uses 'sub' for user_id."""
        token = create_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "u1"
        assert payload["tenant_id"] == "t1"
        assert payload["email"] == "a@b.com"
        assert payload["role"] == "admin"

    def test_decode_token_invalid(self):
        result = decode_token("not.a.valid.token")
        assert result is None

    def test_decode_token_empty(self):
        result = decode_token("")
        assert result is None

    def test_token_contains_expiry(self):
        token = create_token(
            user_id="u1", tenant_id="t1", email="a@b.com", role="admin"
        )
        payload = decode_token(token)
        assert "exp" in payload

    def test_different_users_different_tokens(self):
        t1 = create_token(user_id="u1", tenant_id="t1", email="a@b.com", role="admin")
        t2 = create_token(user_id="u2", tenant_id="t2", email="c@d.com", role="admin")
        assert t1 != t2

"""
Superactive — Shared Rate Limiter

Single Limiter instance shared by server.py and routes/auth.py.
Tests can disable it via `limiter.enabled = False`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

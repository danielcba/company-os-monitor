"""06 - Redis Failure: security controls must fail closed.

When Redis is unavailable:
- is_revoked -> SecurityControlUnavailable (fail-closed)
- consume_refresh_token -> SecurityControlUnavailable (fail-closed)
- revoke -> logs error (non-critical, best-effort)
"""
import asyncio
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from libs.access.token_blacklist import (
    SecurityControlUnavailable,
    TokenBlacklist,
    _NoOpRedis,
)


def test_consume_fail_closed():
    """consume_refresh_token must raise SecurityControlUnavailable when Redis is down."""
    blacklist = TokenBlacklist(redis=_NoOpRedis())
    with pytest.raises(SecurityControlUnavailable):
        asyncio.run(blacklist.consume_refresh_token(
            jti=str(uuid.uuid4()), expires_at=9999999999
        ))


def test_is_revoked_non_critical_fail_open():
    """is_revoked_non_critical must NOT raise when Redis is down."""
    blacklist = TokenBlacklist(redis=_NoOpRedis())
    result = asyncio.run(blacklist.is_revoked_non_critical(jti=str(uuid.uuid4())))
    assert result is False


def test_revoke_does_not_raise():
    """revoke is best-effort; must not raise on Redis failure."""
    blacklist = TokenBlacklist(redis=_NoOpRedis())
    # Should not raise
    asyncio.run(blacklist.revoke(jti=str(uuid.uuid4()), expires_at=9999999999))

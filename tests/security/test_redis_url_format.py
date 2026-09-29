"""Guard: .env.example Redis URLs must keep the password in password position.

redis-py reads bare ``redis://userinfo@host`` as *username*; a password only
exists after a colon (``redis://:password@host``). With compose running Redis
under ``--requirepass``, a username-position credential makes every consumer
fail AUTH with WRONGPASS, leaving the Observation Bus and the JWT stores
inoperativos (correccion_41 runtime evidence). The template is where every
local ``.env`` is copied from, so its URL format is pinned here.
"""
import re
from pathlib import Path

from redis import Redis

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
_BARE_USERINFO = re.compile(r"^redis://[^:/\s]+@")


def _credentialised_redis_urls():
    for raw in ENV_EXAMPLE.read_text().splitlines():
        line = raw.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.startswith("redis://") and "@" in value:
            yield key, value


def test_template_redis_urls_parse_password_not_username():
    pairs = list(_credentialised_redis_urls())
    assert pairs, "expected credentialised redis:// URLs in .env.example"
    for key, value in pairs:
        assert not _BARE_USERINFO.match(value), (
            f"{key}: bare userinfo would be read by redis-py as username"
        )
        kwargs = Redis.from_url(value).connection_pool.connection_kwargs
        assert kwargs.get("password"), f"{key}: credential must parse as password"
        assert not kwargs.get("username"), (
            f"{key}: credential must not parse as username"
        )

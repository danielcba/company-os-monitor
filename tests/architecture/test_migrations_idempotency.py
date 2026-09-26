"""Static idempotency guard for `infrastructure/db-migrations/*.sql`.

`start.sh` re-applies every migration file on each boot with
`psql -v ON_ERROR_STOP=1` and aborts on the first failure
(`apply_migrations || die "DB migrations failed"`), so every statement must be
safe to run more than once.

PostgreSQL has no `ADD CONSTRAINT IF NOT EXISTS`, so an unguarded
`ADD CONSTRAINT` aborts the second run: a documented-idempotent migration
stops the platform from restarting. The sanctioned guard is a `DO $$ ... $$`
block that checks `pg_constraint` first (pattern used by
`h3-learning-execution.sql`).

This test is static (no database required) and covers the failure mode found
by running the full migration set three times against a fresh PostgreSQL 16
database.
"""
import re
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "infrastructure" / "db-migrations"

_DO_BLOCK = re.compile(r"DO\s*\$\$.*?\$\$;", re.DOTALL | re.IGNORECASE)
_LINE_COMMENT = re.compile(r"--[^\n]*")
_ADD_CONSTRAINT = re.compile(r"ADD\s+CONSTRAINT", re.IGNORECASE)


def _unguarded_add_constraints(sql: str) -> bool:
    without_do = _DO_BLOCK.sub(" ", sql)
    without_comments = _LINE_COMMENT.sub(" ", without_do)
    return bool(_ADD_CONSTRAINT.search(without_comments))


def test_migrations_dir_exists():
    assert _MIGRATIONS_DIR.is_dir(), f"missing migrations dir: {_MIGRATIONS_DIR}"


def test_add_constraints_are_guarded():
    offenders = [
        path.name
        for path in sorted(_MIGRATIONS_DIR.glob("*.sql"))
        if _unguarded_add_constraints(path.read_text())
    ]
    assert not offenders, (
        "unguarded ADD CONSTRAINT in migrations (fails on second run, "
        "start.sh dies): " + ", ".join(offenders)
    )

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Make the gateway's top-level `src` package importable for the root test run
# (security/adversarial tests exercise `src.boundary` / `src.service`).
# `src` is an implicit namespace package shared across apps, so this portion
# merges with the context-service `src` portion (added by the e2e test) and
# both `src.activator` and `src.boundary` resolve in the same process.
sys.path.insert(0, str(ROOT / "apps/gateway/api-gateway"))

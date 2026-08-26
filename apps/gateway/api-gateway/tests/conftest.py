import sys
from pathlib import Path

# Ensure the gateway's top-level `src` package is importable for tests run from
# this directory (pytest rootdir becomes apps/gateway/api-gateway because it has
# its own pyproject.toml, so the repo-root conftest sys.path insertion is missed).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

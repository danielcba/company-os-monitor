"""Insight generator package.

Re-exports the public entry point so the service can import it as
``from src.generator import generate_insights`` while the implementation
lives in :mod:`src.generator.generator` (keeps the filename explicit and
avoids reorganizing the whole service).
"""

from .generator import generate_insights

__all__ = ["generate_insights"]

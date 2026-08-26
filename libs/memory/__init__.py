"""Memory Layer package (P7, Learning-family read/compute capability)."""

from libs.memory.consolidation import (
    ConsolidationReport,
    ConsolidationResult,
    ConsolidationStore,
    ConsolidationStoreProtocol,
    CrossTenantConsolidationError,
    DecisionReader,
    TenantScopeError,
    build_consolidation,
    consolidate_decisions,
)

__all__ = [
    "ConsolidationReport",
    "ConsolidationResult",
    "ConsolidationStore",
    "ConsolidationStoreProtocol",
    "CrossTenantConsolidationError",
    "DecisionReader",
    "TenantScopeError",
    "build_consolidation",
    "consolidate_decisions",
]

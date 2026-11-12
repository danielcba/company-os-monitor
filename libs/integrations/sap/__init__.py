"""SAP R/3 integration package (external, non-canonical capability).

D-2026-08-07 / ADR-0002: SAP is an external, non-canonical capability. This
package holds the financial data models (Fase 1), the gateway adapters
(Fase 2) and the bridge from the canonical flow (Fase 3). None of this is
cognitive input; it never bypasses the canonical flow (R3).
"""

from libs.integrations.sap.finance import (
    DEFAULT_CURRENCY,
    AssetFinanceCreate,
    AssetFinanceRecord,
    AssetFinanceStore,
    DowntimeCost,
    WeightedMetric,
    asset_finance_id,
    build_asset_finance,
)
from libs.integrations.sap.sap_bridge import (
    SapBridge,
    SapPostContext,
    SapPostingLogRecord,
    SapPostingLogStore,
    sap_posting_id,
    sap_posting_key,
)
from libs.integrations.sap.sap_gateway import (
    MockSapGateway,
    RfcSapGateway,
    SapConfig,
    SapGateway,
    SapOutcome,
    SapResult,
    build_sap_gateway,
)

__all__ = [
    "AssetFinanceCreate",
    "AssetFinanceRecord",
    "AssetFinanceStore",
    "DEFAULT_CURRENCY",
    "DowntimeCost",
    "MockSapGateway",
    "RfcSapGateway",
    "SapBridge",
    "SapConfig",
    "SapGateway",
    "SapOutcome",
    "SapPostContext",
    "SapPostingLogRecord",
    "SapPostingLogStore",
    "SapResult",
    "WeightedMetric",
    "asset_finance_id",
    "build_asset_finance",
    "build_sap_gateway",
    "sap_posting_id",
    "sap_posting_key",
]

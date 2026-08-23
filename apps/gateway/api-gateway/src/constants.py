"""Shared cognitive constants for the API Gateway.

Centralizes VALID_COGNITIVE_LAYERS, VALID_COGNITIVE_CONCEPTS, and VALID_ACTIONS
to avoid duplication between health.py and audit.py.
"""

VALID_COGNITIVE_LAYERS = {"perception", "reasoning", "confidence", "action", "memory"}
VALID_COGNITIVE_CONCEPTS = {
    "observation", "evidence", "context", "pattern", "anomaly",
    "hypothesis", "insight", "confidence", "recommendation", "decision",
}
VALID_ACTIONS = {
    "captured", "organized", "activated", "detected", "generated",
    "restructured", "calibrated", "proposed", "committed", "executed",
}

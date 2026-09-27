"""Abstract contract for external cognitive tools (LM Studio, etc.).

Implemented by ``LMStudioHypothesisTool`` (external capability, ADR-0002) and
covered by hypothesis-service tests; the canonical pipeline does not invoke an
external tool (no service runtime imports the tool today).
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T')

class CognitiveTool(ABC, Generic[T]):
    @abstractmethod
    async def invoke(self, input: dict) -> T:
        pass
    
    @abstractmethod
    def validate_output(self, output: T) -> bool:
        pass
    
    @abstractmethod
    def available(self) -> bool:
        pass
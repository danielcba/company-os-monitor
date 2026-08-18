"""Abstract contract for external cognitive tools (LM Studio, etc.).

PLANNED for Phase 5+ (LM Studio-assisted Reasoning); not wired to the current
Perception pipeline (Sprints 1-4).
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
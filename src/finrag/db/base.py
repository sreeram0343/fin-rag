from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    """Generic base interface for all database repositories."""

    @abstractmethod
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """Fetch entity by primary key identifier."""
        pass

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Persist or update entity state."""
        pass

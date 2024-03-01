"""
Base configuration backend interface
"""
from typing import Any, Generator
from uuid import UUID

# from ..model import Entry  # Skipped due to circular import


class _Backend:
    """
    Base class for configuration backend.
    """
    @property
    def root(self) -> Any:
        """Returns the root Entry.  Could just use a static node uuid"""
        raise NotImplementedError

    def get_entry(self, meta_id: UUID) -> Any:
        """Get entry with ``meta_id``.  Should attach the backend before returning"""
        raise NotImplementedError

    def _attach_backend(self, entry: Any) -> Any:
        """
        Attach source / backend information so multi-backend works with read-write
        attaches fill method for replaceing uuids with dataclasses
        attaches save method for applying singular change
        """
        raise NotImplementedError

    def save_entry(self, entry: Any):
        """Save a specific entry"""
        raise NotImplementedError

    def delete_entry(self, entry: Any) -> None:
        """Delete meta_id from the system (all instances)"""
        raise NotImplementedError

    def search(self, **search_kwargs) -> Generator[Any, None, None]:
        """Yield a MetaBase objects corresponding matching ``search_kwargs"""
        raise NotImplementedError

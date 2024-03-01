"""Client for superscore.  Used for """
from typing import Any, List

from superscore.backends.core import _Backend
from superscore.model import Entry, Root

ACTIONS = [
    # Always allowed
    'authenticate',
    'search',
    'compare',
    'copy',
    # Usually allowed
    'save',
    # Often restricted
    'delete',
    'apply',
]


class Client:
    backend: _Backend
    authenticator: Any

    def __init__(self, backend=None, **kwargs) -> None:
        # if backend is None, startup default filestore backend
        return

    @classmethod
    def from_config(cls, cfg=None):
        raise NotImplementedError

    def search(self, **post) -> List[Entry]:
        """Search by key-value pair."""
        return self.backend.search(**post)

    def save(self, entry: Entry):
        """Save information in ``entry`` to database"""
        self.backend.save_entry(entry)

    def delete(self, entry: Entry) -> None:
        """Remove item from backend, depending on backend"""
        self.backend.delete_entry(entry)

    def get_root(self) -> Root:
        """Return root Node of databases"""
        return self.backend.root

    def compare(self, entry_l: Entry, entry_r: Entry) -> Any:
        """Compare two entries.  Should be of same type, and return a diff"""
        raise NotImplementedError

    def apply(self, entry: Entry):
        """Apply settings found in ``entry``.  If no values found, no-op"""
        raise NotImplementedError

    def copy(self, source: Entry):
        """Recursively copy ``source``, make new name, clear any stored values"""
        raise NotImplementedError

    def validate(self, entry: Entry):
        """
        Validate ``entry`` is properly formed and able to be inserted into
        the backend.  Includes checks the following:
        - dataclass is valid
        - reachable from root
        - references are not cyclical
        """
        raise NotImplementedError

"""
Backend for configurations backed by files
"""

import contextlib
import json
import logging
import os
import shutil
from typing import Any, Dict, Generator, Optional
from uuid import UUID, uuid4

from apischema import deserialize, serialize

from superscore.backends.core import _Backend
from superscore.model import (Collection, Entry, Parameter, Root, Snapshot,
                              Value)
from superscore.utils import build_abs_path

# write, copy/move mode
# serialize backends

logger = logging.getLogger(__name__)

UUID_ATTR_MAP = {
    Parameter: [],
    Value: [],
    Collection: ['parameters', 'collections'],
    Snapshot: ['values', 'snapshots'],
}


class FilestoreBackend(_Backend):
    """
    Filestore configuration backend.
    Unique aspects:
    entry cache, filled with _load_or_initialize type method
    save method saves entire file, and therefore all Entries

    default method here is to store everything as a flattened dictionary for
    easier access, but serialization must keep Node structure (UUID references
    result in missing data)
    """
    _entry_cache: Dict[UUID, Entry] = {}
    _root: Root

    def __init__(
        self,
        path: str,
        initialize: bool = False,
        cfg_path: Optional[str] = None
    ) -> None:
        self._root = None
        self.path = path
        if cfg_path is not None:
            cfg_dir = os.path.dirname(cfg_path)
            self.path = build_abs_path(cfg_dir, path)
        else:
            self.path = path

        if initialize:
            self.initialize()

    def _load_or_initialize(self) -> Dict[str, Any]:
        """
        Load an existing database or initialize a new one.
        Returns the entry cache for this backend
        """
        if self._root is None:
            try:
                self._root = self.load()
            except FileNotFoundError:
                logger.debug("Initializing new database")
                self.initialize()
                self._root = self.load()

        # flatten create entry cache
        self.flatten_and_cache(self._root)

        return self._entry_cache

    def flatten_and_cache(self, entry: Any):
        """
        Flatten ``node`` recursively, adding them to ``self._entry_cache``.
        Does not replace any dataclass with its uuid
        Currently hard codes structure of Parameters, could maybe refactor later
        """
        attrs = UUID_ATTR_MAP.get(type(entry), [])
        for attr in attrs:
            field = getattr(entry, attr)

            # dicts may need to be supported eventually, but not today
            if isinstance(field, list):
                for item in field:
                    self.maybe_add_to_cache(item)
                    self.flatten_and_cache(item)
            elif field is None:
                continue
            else:
                self.maybe_add_to_cache(field)
                self.flatten_and_cache(field)

    def maybe_add_to_cache(self, item: Any) -> None:
        if isinstance(item, UUID) or item is None:
            return
        meta_id = item.meta_id
        if meta_id in self._entry_cache:
            # duplicate uuids found
            return

        self._entry_cache[meta_id] = self._attach_backend(item)

    def swap_dclass_for_uuids(self) -> None:
        # TODO: Make a method on the dataclasses.  Keep attribute knowledge with dclass
        for entry in self._entry_cache.values():
            for attr in UUID_ATTR_MAP.get(type(entry), []):
                field = getattr(entry, attr)
                if isinstance(field, list):
                    new_list = [getattr(item, 'meta_id', item) for item in field]
                    setattr(entry, attr, new_list)
                elif field is None:
                    continue
                else:
                    setattr(entry, attr, field.meta_id)

    def initialize(self):
        """
        Initialize a new JSON file database.

        Raises
        ------
        PermissionError
            If the JSON file specified by ``path`` already exists.

        Notes
        -----
        This exists because the `.store` and `.load` methods assume that the
        given path already points to a readable JSON file. In order to begin
        filling a new database, an empty but valid JSON file is created.
        """

        # Do not overwrite existing databases
        if os.path.exists(self.path) and os.stat(self.path).st_size > 0:
            raise PermissionError("File {} already exists. Can not initialize "
                                  "a new database.".format(self.path))
        # Dump an empty dictionary
        self.store({})

    def store(self, root_node: Optional[Root] = None) -> None:
        """
        Stash the database in the JSON file.

        This is a two-step process:

        1. Write the database out to a temporary file
        2. Move the temporary file over the previous database.

        Step 2 is an atomic operation, ensuring that the database
        does not get corrupted by an interrupted json.dump.

        Parameters
        ----------
        db : dict
            Dictionary to store in JSON.
        """
        temp_path = self._temp_path()
        # TODO: this doesn't take db, should serialize root directly
        if root_node is None:
            serialized = serialize(Root, self._root)
        else:
            serialized = serialize(Root, Root(meta_id=Root.ROOT_ID))

        try:
            with open(temp_path, 'w') as fd:
                json.dump(serialized, fd, indent=2)

            if os.path.exists(self.path):
                shutil.copymode(self.path, temp_path)
            shutil.move(temp_path, self.path)
        except BaseException as ex:
            logger.debug('JSON db move failed: %s', ex, exc_info=ex)
            # remove temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def _temp_path(self) -> str:
        """
        Return a temporary path to write the json file to during "store".

        Includes a hash for uniqueness
        (in the cases where multiple temp files are written at once).
        """
        directory = os.path.dirname(self.path)
        filename = (
            f"_{str(uuid4())[:8]}"
            f"_{os.path.basename(self.path)}"
        )
        return os.path.join(directory, filename)

    def load(self) -> Optional[Root]:
        """
        Load database from stored path as a nested structure (deserialize as Root)
        """
        with open(self.path) as fp:
            serialized = json.load(fp)

        return deserialize(Root, serialized)

    def _attach_backend(self, entry: Entry) -> Entry:
        """
        Attach source / backend information so multi-backend works with read-write
        """
        entry.backend = self
        return entry

    @property
    def root(self) -> Root:
        with _load_and_store_context(self):
            return self._attach_backend(self._root)

    def get_entry(self, meta_id: str) -> Entry:
        """Return the entry, ensure the backend is attached"""
        return self._attach_backend(self._entry_cache[meta_id])

    def save_entry(self, entry: Entry):
        """Save specific entry into database.  Assumes connections are made properly"""
        return
        # with _load_and_store_context as db:
        #     # Ensure uuids are filled, links are proper
        #     # make sure it's reachable from root node?
        #     pass

    def delete_entry(self, entry: Entry) -> None:
        """Delete meta_id from the system (all instances)"""
        with _load_and_store_context(self) as db:
            # find and remove all references to meta_id
            for entry in self._entry_cache.values():
                for attr in UUID_ATTR_MAP[type(entry)]:
                    value = getattr(entry, attr)
                    if isinstance(value, list):
                        # Find entry with ``meta_id`` in list and remove it
                        continue

                    else:
                        if value.meta_id == '':
                            setattr(entry, attr, None)

            # remove from entry cache
            db.pop('')

    def search(self, **search_kwargs) -> Generator[Any, None, None]:
        raise NotImplementedError

    def clear_cache(self) -> None:
        """Clear the loaded cache and stored root"""
        self._entry_cache = {}
        self._root = None


@contextlib.contextmanager
def _load_and_store_context(
    backend: FilestoreBackend
) -> Generator[Dict[UUID, Any], None, None]:
    """
    Context manager used to load, and optionally store the JSON database.
    Yields the flattened entry cache
    """
    db = backend._load_or_initialize()
    yield db
    backend.store()

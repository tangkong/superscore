import json
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import apischema

logger = logging.getLogger(__name__)

@dataclass
class SavedFilter:
    name: str
    types: List[str]
    name_filter: str
    desc_filter: str
    pv_filter: str
    start_time: str
    end_time: str


class SavedFiltersManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SavedFiltersManager, cls).__new__(cls)
            cls._instance.filters = []
            cls._instance.load_from_disk()
        return cls._instance

    def get_filters_path(self) -> str:
        """Return the path to the filters configuration file."""
        return os.path.expanduser("~/.superscore/filters.json")

    def load_from_disk(self) -> None:
        """Load saved filters from disk."""
        path = self.get_filters_path()
        if not os.path.exists(path):
            self.filters = []
            return

        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self.filters = [apischema.deserialize(SavedFilter, item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load filters from {path}: {e}")
            self.filters = []

    def save_to_disk(self) -> None:
        """Save filters to disk."""
        path = self.get_filters_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, 'w') as f:
                data = [apischema.serialize(item) for item in self.filters]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save filters to {path}: {e}")

    def add_filter(self, filter_obj: SavedFilter) -> None:
        self.filters.append(filter_obj)
        self.save_to_disk()

    def get_filters(self) -> List[SavedFilter]:
        return self.filters

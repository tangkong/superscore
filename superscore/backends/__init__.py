__all__ = ["BACKENDS", "DEFAULT_BACKEND"]

import logging

logging = logging.getLogger(__name__)


def _get_backend(backend: str):
    if backend == 'filestore':
        from .filestore import FilestoreBackend
        return FilestoreBackend

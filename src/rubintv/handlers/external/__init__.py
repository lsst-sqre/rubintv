"""Externally-accessible endpoint handlers that serve relative to
``/<app-name>/``.
"""

__all__ = ["get_index"]

from rubintv.handlers.external.index import get_index
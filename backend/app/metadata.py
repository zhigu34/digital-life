"""Compatibility facade for the Shows metadata domain.

New code should import from :mod:`app.shows.metadata`. This module keeps the
historical import and monkeypatch surface used by tests and downstream callers.
"""

import sys

from app.shows import metadata as _impl

router = _impl.router
BANGUMI_API = _impl.BANGUMI_API
TMDB_API = _impl.TMDB_API
TMDB_IMAGE = _impl.TMDB_IMAGE
USER_AGENT = _impl.USER_AGENT
TIMEOUT_SECONDS = _impl.TIMEOUT_SECONDS
MAX_RESULTS = _impl.MAX_RESULTS
TMDB_DETAIL_RESULTS = _impl.TMDB_DETAIL_RESULTS
SUBJECT_TYPES = _impl.SUBJECT_TYPES
TMDB_KIND = _impl.TMDB_KIND
TMDB_TV_STATUS = _impl.TMDB_TV_STATUS
TMDB_MOVIE_STATUS = _impl.TMDB_MOVIE_STATUS
POSTER_HOSTS = _impl.POSTER_HOSTS
MAX_POSTER_BYTES = _impl.MAX_POSTER_BYTES
LOCAL_POSTER = _impl.LOCAL_POSTER

_reason = _impl._reason
_release_year = _impl._release_year
_send = _impl._send
_send_resilient = _impl._send_resilient
search_bangumi = _impl.search_bangumi
search_tmdb = _impl.search_tmdb
lookup_metadata = _impl.lookup_metadata
fetch_image = _impl.fetch_image
sniff_image = _impl.sniff_image
show_poster = _impl.show_poster
upload_poster = _impl.upload_poster

# Route implementation call sites through this facade when it is imported so
# legacy monkeypatches (for example app.metadata._send) keep working.
_impl.set_compat_api(sys.modules[__name__])

__all__ = [
    "BANGUMI_API",
    "LOCAL_POSTER",
    "MAX_POSTER_BYTES",
    "MAX_RESULTS",
    "POSTER_HOSTS",
    "SUBJECT_TYPES",
    "TIMEOUT_SECONDS",
    "TMDB_API",
    "TMDB_DETAIL_RESULTS",
    "TMDB_IMAGE",
    "TMDB_KIND",
    "TMDB_MOVIE_STATUS",
    "TMDB_TV_STATUS",
    "USER_AGENT",
    "fetch_image",
    "lookup_metadata",
    "router",
    "search_bangumi",
    "search_tmdb",
    "show_poster",
    "sniff_image",
    "upload_poster",
]

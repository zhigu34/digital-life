"""The reverse proxy must not undercut the application's own upload limit.

`frontend/nginx.conf` shipped a server-level `client_max_body_size 1m` while the
app accepts posters up to `MAX_POSTER_BYTES` (5 MB). Every real phone photo was
therefore refused at the edge with an nginx 413 page that the UI could only
report as a generic failure — and never in local development, where Vite proxies
the request without a body limit. This test pins the two numbers together.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NGINX_CONF = ROOT / 'frontend/nginx.conf'
METADATA = ROOT / 'backend/app/shows/metadata.py'
UNITS = {'': 1, 'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3}


def size_in_bytes(value):
    match = re.fullmatch(r'(\d+)([kmg]?)', value.strip().lower())
    if not match:
        raise AssertionError(f'Cannot parse nginx size {value!r}')
    return int(match.group(1)) * UNITS[match.group(2)]


def poster_limit():
    match = re.search(r'^MAX_POSTER_BYTES\s*=\s*([\d_]+)', METADATA.read_text(), re.MULTILINE)
    if not match:
        raise AssertionError('MAX_POSTER_BYTES is no longer defined in shows/metadata.py')
    return int(match.group(1).replace('_', ''))


def api_location_block():
    text = NGINX_CONF.read_text()
    start = text.index('location /api/ {')
    # Every directive in that block is single-line and there is no nesting.
    return text[start:text.index('}', start)]


def directive(block, name):
    match = re.search(rf'{name}\s+([^;]+);', block)
    return match.group(1).strip() if match else None


class UploadLimitTest(unittest.TestCase):
    def test_api_location_allows_a_full_poster_upload(self):
        configured = directive(api_location_block(), 'client_max_body_size')
        self.assertIsNotNone(
            configured,
            'location /api/ must set client_max_body_size above the server default, '
            'otherwise poster uploads are rejected by the proxy',
        )
        self.assertGreaterEqual(
            size_in_bytes(configured), poster_limit(),
            'nginx must accept at least MAX_POSTER_BYTES so uploads reach the backend',
        )

    def test_static_requests_keep_the_tight_default(self):
        server_level = directive(NGINX_CONF.read_text(), 'client_max_body_size')
        self.assertIsNotNone(server_level, 'the server-level body limit must stay explicit')
        self.assertLess(
            size_in_bytes(server_level), poster_limit(),
            'raise the limit in location /api/ only; static requests need no large body',
        )


if __name__ == '__main__':
    unittest.main()

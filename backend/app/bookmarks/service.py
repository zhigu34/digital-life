"""Business rules shared by the bookmark endpoints."""

import html
import ipaddress
import logging
import re
import socket
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bookmarks.schemas import MAX_TITLE_LENGTH
from app.models import Bookmark

logger = logging.getLogger(__name__)
USER_AGENT = "zhigu34-digital-life (self-hosted; title lookup on user request)"
TIMEOUT_SECONDS = 8.0
# Read at most this much of a page: only the <title> is needed.
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
TITLE_PATTERN = re.compile(rb"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
TAG_PATTERN = re.compile(r"<[^>]+>")


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def owned_bookmark(db: Session, item_id: int, user_id: int) -> Bookmark:
    bookmark = db.scalar(
        select(Bookmark).where(Bookmark.id == item_id, Bookmark.user_id == user_id)
    )
    if bookmark is None:
        raise HTTPException(404, "记录不存在")
    return bookmark


def blocked_host(hostname: str) -> bool:
    """True when a host must not be fetched: localhost, LAN or reserved space.

    The service runs on the user's own NAS, so reaching 192.168.x.x or 127.0.0.1
    from the backend is exactly the SSRF this has to prevent. Domain names are
    resolved first, otherwise a public name pointing at a private address would
    slip through.
    """
    candidate = hostname.strip().strip("[]")
    try:
        addresses = [ipaddress.ip_address(candidate)]
    except ValueError:
        try:
            resolved = socket.getaddrinfo(candidate, None)
        except (socket.gaierror, UnicodeError, ValueError):
            return True
        parsed = []
        for info in resolved:
            try:
                parsed.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                return True
        if not parsed:
            return True
        addresses = parsed
    return any(_private(address) for address in addresses)


def _private(address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def fetch_title(url: str) -> str:
    """Fetch a page and return its <title>, following redirects by hand.

    Every hop is re-checked, so a public URL cannot redirect into the LAN.
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        if blocked_host(parts.hostname or ""):
            raise HTTPException(422, "不支持抓取内网或保留地址，请手动填写标题")
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            try:
                with client.stream("GET", current) as response:
                    content_type = response.headers.get("content-type", "")
                    if not content_type.split(";", 1)[0].strip().lower().startswith("text/"):
                        raise HTTPException(422, "该链接不是网页，请手动填写标题")
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPException(422, "目标网页重定向到了无效地址")
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        raise HTTPException(
                            422, f"目标网页返回 {response.status_code}，请手动填写标题"
                        )
                    chunks = []
                    size = 0
                    for chunk in response.iter_bytes():
                        chunks.append(chunk)
                        size += len(chunk)
                        if size >= MAX_BYTES:
                            break
                    encoding = response.encoding or "utf-8"
            except httpx.HTTPError as error:
                logger.info(
                    "Bookmark title lookup failed for %s: %s", current, type(error).__name__
                )
                raise HTTPException(422, "无法访问该网页，请手动填写标题") from None
        body = b"".join(chunks)
        match = TITLE_PATTERN.search(body)
        if match is None:
            raise HTTPException(422, "该网页没有标题，请手动填写")
        title = _decode(match.group(1), encoding)
        if not title:
            raise HTTPException(422, "该网页没有标题，请手动填写")
        return title[:MAX_TITLE_LENGTH]
    raise HTTPException(422, "重定向次数过多，请手动填写标题")


def _decode(raw: bytes, encoding: str) -> str:
    try:
        text = raw.decode(encoding, errors="replace")
    except (LookupError, TypeError):
        text = raw.decode("utf-8", errors="replace")
    text = TAG_PATTERN.sub(" ", html.unescape(text))
    # Collapse the whitespace a pretty-printed <title> usually carries.
    return re.sub(r"\s+", " ", text).strip()

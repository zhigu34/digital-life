"""Bookmark request and response models.

The URL is validated here rather than at render time: links are shown as
`<a href>` in the browser, so a `javascript:` or `data:` URL would otherwise
become stored XSS.
"""

import re
from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import Notes, Payload, StrictBool, patch_schema

MAX_URL_LENGTH = 2048
MAX_TITLE_LENGTH = 160
ALLOWED_SCHEMES = ("http", "https")


def clean_url(value) -> str:
    """Validate a bookmark URL and return it in normalised form."""
    if not isinstance(value, str):
        raise ValueError("网址必须是字符串")
    url = value.strip()
    if not url:
        raise ValueError("网址不能为空")
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"网址长度不能超过 {MAX_URL_LENGTH} 个字符")
    # A space inside the URL would let a request line or header be split when
    # the backend later fetches the page for a title lookup.
    if any(character.isspace() for character in url):
        raise ValueError("网址不能包含空格")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("网址必须以 http:// 或 https:// 开头")
    if not parts.netloc or not parts.hostname:
        raise ValueError("网址缺少域名")
    if not re.fullmatch(r"[A-Za-z0-9._~%:\-]+", parts.hostname.lstrip("[").rstrip("]")):
        raise ValueError("网址域名无效")
    return url


class BookmarkPayload(Payload):
    url: Annotated[str, Field(max_length=MAX_URL_LENGTH)]
    title: Annotated[str, Field(min_length=1, max_length=MAX_TITLE_LENGTH)]
    note: Notes = ""
    folder: Annotated[str, Field(max_length=60)] | None = None
    starred: StrictBool = False

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return clean_url(value)

    @field_validator("folder", mode="before")
    @classmethod
    def blank_folder_is_none(cls, value):
        # The folder dropdown posts "" for "no group"; store that as NULL so the
        # index and grouping filter only ever compare against one shape.
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class BookmarkView(BookmarkPayload):
    id: int
    visit_count: int
    last_visited_at: datetime | None
    created_at: datetime


BookmarkPatch = patch_schema("BookmarkPatch", BookmarkPayload)


class UrlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return clean_url(value)


class TitleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str

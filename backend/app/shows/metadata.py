"""Shows metadata lookup and poster handling (Bangumi / TMDB)."""

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.auth import Identity, authenticated
from app.database import get_db
from app.shows.schemas import ResourceId, ShowView
from app.shows.service import owned_show

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shows", tags=["metadata"])
BANGUMI_API = "https://api.bgm.tv"
TMDB_API = "https://api.themoviedb.org/3"
TMDB_IMAGE = "https://image.tmdb.org/t/p/w342"
USER_AGENT = "zhigu34-digital-life (self-hosted; no automated crawling)"
TIMEOUT_SECONDS = 8.0
MAX_RESULTS = 8
TMDB_DETAIL_RESULTS = 6
SUBJECT_TYPES = {"anime": [2], "tv": [6], "movie": [6]}
TMDB_KIND = {"anime": "tv", "tv": "tv", "movie": "movie"}
TMDB_TV_STATUS = {
    "Returning Series": "airing",
    "Ended": "ended",
    "Canceled": "ended",
    "In Production": "upcoming",
    "Pilot": "upcoming",
}
TMDB_MOVIE_STATUS = {"Released": "released"}
POSTER_HOSTS = {"image.tmdb.org", "lain.bgm.tv"}
MAX_POSTER_BYTES = 5_000_000
LOCAL_POSTER = "local:upload"


def _reason(error: Exception) -> str:
    text = str(error).split("\n", 1)[0]
    return f"{type(error).__name__}: {text[:180]}"


def _release_year(value) -> int | None:
    if not isinstance(value, str) or len(value) < 4 or not value[:4].isdigit():
        return None
    year = int(value[:4])
    return year if 1000 <= year <= 9999 else None


def _send(method: str, url: str, *, transport: httpx.BaseTransport | None = None, **kwargs):
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS, transport=transport
    ) as client:
        return getattr(client, method)(url, **kwargs)


def _send_resilient(method: str, url: str, **kwargs):
    try:
        return _send(method, url, **kwargs)
    except httpx.ConnectError as error:
        logger.info("Retrying %s over IPv4 only after %s", url, type(error).__name__)
        return _send(
            method,
            url,
            transport=httpx.HTTPTransport(local_address="0.0.0.0"),
            **kwargs,
        )


def search_bangumi(keyword: str, subject_types: list[int]) -> list[dict]:
    response = _send_resilient(
        "post",
        f"{BANGUMI_API}/v0/search/subjects",
        json={"keyword": keyword, "filter": {"type": subject_types}, "limit": MAX_RESULTS},
    )
    response.raise_for_status()
    results = []
    for item in response.json().get("data", []):
        episodes = item.get("total_episodes") or item.get("eps") or 0
        images = item.get("images") or {}
        source_id = item.get("id")
        air_date = item.get("date")
        results.append(
            {
                "source": "bangumi",
                "source_id": source_id,
                "source_url": f"https://bgm.tv/subject/{source_id}" if source_id else None,
                "title": item.get("name_cn") or item.get("name") or keyword,
                "original_title": item.get("name"),
                "air_date": air_date,
                "release_year": _release_year(air_date),
                "total_episodes": episodes or None,
                "platform": item.get("platform"),
                "image": images.get("common") or images.get("large"),
                "seasons": None,
                "air_status": None,
            }
        )
    return results


def search_tmdb(keyword: str, kind: str, api_key: str) -> list[dict]:
    search = _send_resilient(
        "get",
        f"{TMDB_API}/search/{kind}",
        params={
            "api_key": api_key,
            "query": keyword,
            "language": "zh-CN",
            "include_adult": "false",
        },
    )
    search.raise_for_status()
    results = []
    for item in search.json().get("results", [])[:TMDB_DETAIL_RESULTS]:
        source_id = item.get("id")
        air_date = item.get("first_air_date") or item.get("release_date")
        entry = {
            "source": "tmdb",
            "source_id": source_id,
            "source_url": f"https://www.themoviedb.org/{kind}/{source_id}" if source_id else None,
            "title": item.get("name") or item.get("title") or keyword,
            "original_title": item.get("original_name") or item.get("original_title"),
            "air_date": air_date,
            "release_year": _release_year(air_date),
            "poster": item.get("poster_path"),
        }
        detail: dict = {}
        try:
            detail_response = _send_resilient(
                "get",
                f"{TMDB_API}/{kind}/{item['id']}",
                params={"api_key": api_key, "language": "zh-CN"},
            )
            detail_response.raise_for_status()
            detail = detail_response.json()
        except httpx.HTTPError:
            detail = {}
        if kind == "tv":
            entry.update(
                {
                    "total_episodes": detail.get("number_of_episodes") or None,
                    "seasons": detail.get("number_of_seasons") or None,
                    "air_status": TMDB_TV_STATUS.get(detail.get("status", "")),
                    "platform": None,
                }
            )
        else:
            entry.update(
                {
                    "total_episodes": 1,
                    "seasons": None,
                    "air_status": TMDB_MOVIE_STATUS.get(detail.get("status", ""), "upcoming")
                    if detail
                    else None,
                    "platform": None,
                }
            )
        poster = entry.pop("poster", None)
        entry["image"] = f"{TMDB_IMAGE}{poster}" if poster else None
        results.append(entry)
    return results


@router.get("/metadata")
def lookup_metadata(
    request: Request,
    keyword: str,
    media_type: str = "anime",
    source: str = "bangumi",
    identity: Identity = Depends(authenticated),
):
    settings = request.app.state.settings
    if settings.metadata_disabled:
        raise HTTPException(503, "元数据获取未启用（DIGITAL_LIFE_DISABLE_METADATA）")
    if media_type not in SUBJECT_TYPES:
        raise HTTPException(400, "不支持的作品类型")
    if source not in {"bangumi", "tmdb"}:
        raise HTTPException(400, "未知信息源")
    if source == "tmdb" and not settings.tmdb_api_key:
        raise HTTPException(400, "未配置 DIGITAL_LIFE_TMDB_API_KEY，无法使用 TMDB")
    keyword = keyword.strip()
    if not 1 <= len(keyword) <= 80:
        raise HTTPException(422, "搜索关键词需要 1–80 个字符")
    provider = "TMDB" if source == "tmdb" else "Bangumi"
    try:
        if source == "tmdb":
            results = search_tmdb(keyword, TMDB_KIND[media_type], settings.tmdb_api_key)
        else:
            results = search_bangumi(keyword, SUBJECT_TYPES[media_type])
        return {"results": results}
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Metadata lookup via %s failed", provider)
        raise HTTPException(502, f"暂时无法连接信息源（{provider}）：{_reason(error)}") from error


def fetch_image(url: str) -> tuple[bytes, str]:
    response = _send_resilient("get", url, follow_redirects=True)
    response.raise_for_status()
    content = response.content
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if len(content) > MAX_POSTER_BYTES:
        raise ValueError("poster too large")
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("unexpected poster content type")
    return content, content_type


def sniff_image(content: bytes) -> str:
    if content.startswith(b"\x89PNG"):
        return "image/png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return ""


@router.get("/{item_id}/poster")
def show_poster(
    item_id: ResourceId,
    request: Request,
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    show = owned_show(db, item_id, identity.user.id)
    if not show.poster_path:
        raise HTTPException(404, "该记录没有封面")
    settings = request.app.state.settings
    cache_dir = settings.data_dir / "posters"
    cached = cache_dir / f"{show.id}.img"
    if show.poster_path == LOCAL_POSTER:
        if not cached.is_file():
            raise HTTPException(404, "封面文件缺失，请重新上传")
    else:
        host = urlparse(show.poster_path).hostname or ""
        if host not in POSTER_HOSTS:
            raise HTTPException(400, "封面来源不受支持")
        if not cached.is_file():
            try:
                content, content_type = fetch_image(show.poster_path)
            except ValueError as error:
                logger.warning("Poster rejected: %s", error)
                raise HTTPException(502, f"封面文件无效：{error}") from None
            except Exception as error:
                logger.exception("Poster download failed for show %s", show.id)
                raise HTTPException(502, f"暂时无法获取封面：{_reason(error)}") from error
            cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            staged = cache_dir / f".{show.id}.tmp"
            staged.write_bytes(content)
            staged.replace(cached)
    content = cached.read_bytes()
    return Response(
        content,
        media_type=sniff_image(content),
        headers={"Cache-Control": "private, max-age=604800"},
    )


@router.put("/{item_id}/poster", response_model=ShowView)
async def upload_poster(
    item_id: ResourceId,
    request: Request,
    file: UploadFile = File(...),
    identity: Identity = Depends(authenticated),
    db: Session = Depends(get_db),
):
    show = owned_show(db, item_id, identity.user.id)
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传的文件为空")
    if len(content) > MAX_POSTER_BYTES:
        raise HTTPException(413, f"封面不能超过 {MAX_POSTER_BYTES // 1_000_000} MB")
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        content_type = sniff_image(content)
        if not content_type:
            raise HTTPException(415, "仅支持 JPEG / PNG / WebP 图片")
    settings = request.app.state.settings
    cache_dir = settings.data_dir / "posters"
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = cache_dir / f".{show.id}.tmp"
    staged.write_bytes(content)
    staged.replace(cache_dir / f"{show.id}.img")
    show.poster_path = LOCAL_POSTER
    db.commit()
    db.refresh(show)
    return show

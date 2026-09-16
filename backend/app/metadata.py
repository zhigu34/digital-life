"""Optional, manually-triggered show metadata lookup via the public Bangumi API.

The workspace itself never requires internet access: this module only runs when
the user explicitly clicks search in the show form, and operators can turn it
off entirely with DIGITAL_LIFE_DISABLE_METADATA=true.
"""

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import Identity, authenticated

router = APIRouter(prefix="/api/shows", tags=["metadata"])
BANGUMI_API = "https://api.bgm.tv"
USER_AGENT = "zhigu34-digital-life (self-hosted; no automated crawling)"
TIMEOUT_SECONDS = 8.0
MAX_RESULTS = 8
# Bangumi subject types: 2 = anime, 6 = real-person shows (drama and film).
SUBJECT_TYPES = {"anime": [2], "tv": [6], "movie": [6]}


def search_bangumi(keyword: str, subject_types: list[int]) -> list[dict]:
    # Honors standard proxy environment variables so hosts behind an outbound
    # proxy can still reach the API; hosts without one connect directly.
    with httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS
    ) as client:
        response = client.post(
            f"{BANGUMI_API}/v0/search/subjects",
            json={
                "keyword": keyword,
                "filter": {"type": subject_types},
                "limit": MAX_RESULTS,
            },
        )
    response.raise_for_status()
    results = []
    for item in response.json().get("data", []):
        episodes = item.get("total_episodes") or item.get("eps") or 0
        results.append(
            {
                "source": "bangumi",
                "source_id": item.get("id"),
                "title": item.get("name_cn") or item.get("name") or keyword,
                "original_title": item.get("name"),
                "air_date": item.get("date"),
                "total_episodes": episodes or None,
                "platform": item.get("platform"),
            }
        )
    return results


@router.get("/metadata")
def lookup_metadata(
    request: Request,
    keyword: str,
    media_type: str = "anime",
    identity: Identity = Depends(authenticated),
):
    if request.app.state.settings.metadata_disabled:
        raise HTTPException(503, "元数据获取未启用（DIGITAL_LIFE_DISABLE_METADATA）")
    subject_types = SUBJECT_TYPES.get(media_type)
    if subject_types is None:
        raise HTTPException(400, "不支持的作品类型")
    keyword = keyword.strip()
    if not 1 <= len(keyword) <= 80:
        raise HTTPException(422, "搜索关键词需要 1–80 个字符")
    try:
        return {"results": search_bangumi(keyword, subject_types)}
    except HTTPException:
        raise
    except Exception:
        # Any outbound failure (DNS, proxy, TLS, upstream status) is simply an
        # unavailable optional service; it must never surface as a 500.
        raise HTTPException(502, "暂时无法连接信息源（Bangumi），请稍后再试") from None

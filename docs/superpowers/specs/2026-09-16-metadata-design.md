# 追番信息刮削设计（用户已确认，2026-09-16）

目标：添加动漫时可选"联网搜索"，从 Bangumi 开放接口取回候选，点选后回填名称与总集数，减少手动输入。

## 边界（对既有约定的调整）

- 核心功能仍完全不依赖联网；本功能仅在用户于追剧创建表单中主动点击时调用一次外部接口，失败或离线只影响该按钮（返回 502/503 就地提示），不影响任何其他能力。
- 数据源只用 Bangumi 开放搜索接口（`POST /v0/search/subjects`）：免 API key、无爬虫、请求带自述 User-Agent、单次最多 8 条、8 秒超时。类型映射：动漫→type 2，剧集/电影→type 6（三次元，含华语剧/日剧/欧美剧/电影，结果带 platform 分类标签）。
- 尊重标准代理环境变量（httpx `trust_env`），NAS 无代理直连；运营者可用 `DIGITAL_LIFE_DISABLE_METADATA=true` 整体关闭（接口返回 503）。
- 不自动写入、不后台同步、不保存封面；用户点选仅回填表单字段，保存仍走原有校验。

## 接口

- `GET /api/shows/metadata?keyword=1..80&media_type=anime|tv|movie`（登录会话，只读）→ `{results: [{source,source_id,title,original_title,air_date,total_episodes,platform}]}`，name_cn 优先作为标题。
- 未登录 401；media_type 不在三种类型内 400；关键词空白/超长 422；上游任何故障统一 502（不泄漏 500）；被禁用 503。
- 路由注册在通用 `/api/shows/{id}` 之前。

## 界面

- 追剧创建弹窗（非编辑态）按所选类型显示"联网搜索动漫/剧集/电影信息"文字按钮；结果列表最多 8 条（标题 + 分类标签 + 集数 + 首播日），点选回填名称与总集数，可继续编辑。

## 验证

- pytest：认证、参数校验、标准化结果（stub `search_bangumi`）、上游异常映射 502、禁用开关 503。
- Playwright：路由桩替换元数据接口，真实 UI 完成 搜索→点选→回填→保存→列表可见。
- 真实接口冒烟：本机经代理实测关键词"芙莉莲"返回正确候选（28 集条目）。

## 2026-09-16 补充：剧集与电影

同日扩展支持 tv/movie（Bangumi type 6 三次元分类，经真实接口验证：漫长的季节→华语剧 12 集、流浪地球→电影、绝命毒师→欧美剧均正确）。media_type 校验放宽为三种类型；结果新增 platform 字段并在 UI 显示为分类标签；电影条目的 total_episodes 通常为 1，回填后与"看完一集"按钮语义一致。

## 2026-09-16 再补充：TMDB 与封面（用户确认方向修订）

用户明确要求两套数据源独立可选（而非按类型自动分流），且希望刮削带回封面、季数与完结/连载状态：

- `source=bangumi|tmdb` 为显式参数，界面提供切换；TMDB 在 themoviedb.org 免费申请 v3 API Key 填入 `.env` 的 `DIGITAL_LIFE_TMDB_API_KEY` 后可用，未配置时选择 TMDB 返回 400 就地提示。
- TMDB：`/3/search/{tv|movie}`（zh-CN）+ 逐候选拉 `/3/{kind}/{id}` 详情获得 `number_of_seasons`、`status`（Returning Series→airing、Ended/Canceled→ended、其余→upcoming；电影 Released→released）、`number_of_episodes`；动画在 TMDB 中按 TV 检索。详情失败仅降级该候选。Bangumi 动画在 TMDB 的 zh-CN 数据弱，仍可直接选 Bangumi。
- 封面：两条源都返回 image URL（TMDB image.tmdb.org、Bangumi lain.bgm.tv）。Show 新增 `source/source_id/poster_path/seasons/air_status`（迁移 `0004`，CLI 恢复版本同步 0004）。`GET /api/shows/{id}/poster` 由后端从白名单主机下载（≤5MB，JPEG/PNG/WebP 嗅探），缓存数据目录 `posters/`，私有缓存 7 天；浏览器无需访问外网，避免国内访问 TMDB CDN 受限。poster_path 属用户可写字段，下载前做主机白名单校验防 SSRF；封面是可再生缓存，不入 SQLite 备份。
- 卡片展示封面、`N 季`与完结/连载标签；搜索结果行含缩略图（加载失败自动隐藏）与状态徽标。

验证：TMDB 部分以 stub 单测覆盖（无法在无 key 环境实测真实接口，待 NAS 填 key 后由用户验证）；Bangumi 封面链路真实冒烟通过（搜索带图 → 创建 → 代理下载 51KB JPEG → 磁盘缓存命中）。

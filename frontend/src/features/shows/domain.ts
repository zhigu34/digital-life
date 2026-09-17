import type { Show } from "../../types";

export type ShowFilter = "all" | Show["status"];
export type ShowTypeGroup = { type: Show["media_type"]; items: Show[] };

export function filterShows(shows: Show[], query: string, filter: ShowFilter): Show[] {
  const needle = query.trim().toLowerCase();
  return shows.filter(
    (item) => item.title.toLowerCase().includes(needle) && (filter === "all" || item.status === filter),
  );
}

export function groupShowsByType(shows: Show[]): ShowTypeGroup[] {
  const order: Show["media_type"][] = ["tv", "anime", "movie"];
  return order
    .map((type) => ({ type, items: shows.filter((item) => item.media_type === type) }))
    .filter((group) => group.items.length > 0);
}

export function showProgressPercent(show: Pick<Show, "progress" | "total">): number {
  if (!show.total) return 0;
  return Math.min(100, Math.max(0, (show.progress / show.total) * 100));
}

export function showAdvanceDisabled(show: Pick<Show, "progress" | "total">, busy: boolean): boolean {
  return busy || (show.total !== null && show.progress >= show.total);
}

export interface ShowFormDraft {
  id?: number;
  created_at?: string;
  title: string;
  notes: string;
  media_type: Show["media_type"];
  status: Show["status"];
  progress: number | string;
  total: number | string | null;
  score: number | string | null;
  update_weekday: number | string | null;
  source?: Show["source"] | "";
  source_id?: number | string | null;
  source_url?: string | null;
  poster_path?: string | null;
  seasons?: number | string | null;
  air_status?: Show["air_status"] | "";
  release_year?: number | string | null;
  completed_on?: string | null;
}

export interface ShowMetadataResult {
  source: "bangumi" | "tmdb";
  source_id: number;
  source_url: string | null;
  title: string;
  original_title: string | null;
  air_date: string | null;
  release_year: number | null;
  total_episodes: number | null;
  platform: string | null;
  image: string | null;
  seasons: number | null;
  air_status: "airing" | "ended" | "upcoming" | "released" | null;
}

export type ShowMetadataPatch = Pick<
  ShowFormDraft,
  "title" | "total" | "source" | "source_id" | "source_url" | "poster_path" | "seasons" | "air_status" | "release_year"
>;

export type NormalizeShowResult =
  | { data: Omit<Show, "id">; error: null }
  | { data: null; error: string };

function numberOrNull(value: unknown): number | null {
  return value === "" || value === null || value === undefined ? null : Number(value);
}

function stringOrNull<T extends string>(value: T | "" | null | undefined): T | null {
  return value === "" || value === null || value === undefined ? null : value;
}

export function normalizeShowPayload(draft: ShowFormDraft): NormalizeShowResult {
  const data: Omit<Show, "id"> = {
    title: draft.title,
    notes: draft.notes,
    media_type: draft.media_type,
    status: draft.status,
    progress: Number(draft.progress),
    total: numberOrNull(draft.total),
    score: numberOrNull(draft.score),
    update_weekday: numberOrNull(draft.update_weekday),
    source: stringOrNull(draft.source),
    source_id: numberOrNull(draft.source_id),
    source_url: stringOrNull(draft.source_url),
    poster_path: stringOrNull(draft.poster_path),
    seasons: numberOrNull(draft.seasons),
    air_status: stringOrNull(draft.air_status),
    release_year: numberOrNull(draft.release_year),
    completed_on: stringOrNull(draft.completed_on),
  };
  if (data.total !== null && data.progress > data.total) return { data: null, error: "已看进度不能大于总集数" };
  return { data, error: null };
}

export function showMetadataPatch(result: ShowMetadataResult): ShowMetadataPatch {
  return {
    title: result.title,
    total: result.total_episodes ?? "",
    source: result.source,
    source_id: result.source_id,
    source_url: result.source_url ?? "",
    poster_path: result.image ?? "",
    seasons: result.seasons ?? "",
    air_status: result.air_status ?? "",
    release_year: result.release_year ?? "",
  };
}

export function applyShowMetadata(draft: ShowFormDraft, result: ShowMetadataResult): ShowFormDraft {
  return { ...draft, ...showMetadataPatch(result) };
}

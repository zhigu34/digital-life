import { api, uploadPoster } from "../../api";
import type { Show } from "../../types";
import type { ShowMetadataResult } from "./domain";

export const listShows = () => api<Show[]>("/shows");
export const createShow = (data: Record<string, unknown>) => api<Show>("/shows", "POST", data);
export const updateShow = (id: number, data: Record<string, unknown>) => api<Show>(`/shows/${id}`, "PATCH", data);
export const deleteShow = (id: number) => api<void>(`/shows/${id}`, "DELETE");
export const advanceShow = (id: number) => api<Show>(`/shows/${id}/advance`, "POST");
export const searchShowMetadata = (
  keyword: string,
  mediaType: Show["media_type"],
  source: "bangumi" | "tmdb",
) => api<{ results: ShowMetadataResult[] }>(
  `/shows/metadata?keyword=${encodeURIComponent(keyword)}&media_type=${mediaType}&source=${source}`,
);
export const uploadShowPoster = (id: number, file: File) => uploadPoster(`/shows/${id}/poster`, file);

import { api } from "../../api";
import type { Bookmark } from "../../types";

export const listBookmarks = () => api<Bookmark[]>("/bookmarks");
export const createBookmark = (data: Record<string, unknown>) =>
  api<Bookmark>("/bookmarks", "POST", data);
export const updateBookmark = (id: number, data: Record<string, unknown>) =>
  api<Bookmark>(`/bookmarks/${id}`, "PATCH", data);
export const deleteBookmark = (id: number) => api<void>(`/bookmarks/${id}`, "DELETE");
export const visitBookmark = (id: number) => api<Bookmark>(`/bookmarks/${id}/visit`, "POST");
/** Only runs when the user presses "获取标题"; the backend refuses LAN targets. */
export const fetchBookmarkTitle = (url: string) =>
  api<{ title: string }>("/bookmarks/title", "POST", { url });

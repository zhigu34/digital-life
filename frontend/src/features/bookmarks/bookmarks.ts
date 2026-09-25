import type { Bookmark } from "../../types";

export interface BookmarkGroup {
  folder: string | null;
  items: Bookmark[];
}

/** `undefined` means every group; `""` means the ungrouped rows. */
export type FolderFilter = string | undefined;

export function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return "";
  }
}

/**
 * The browser loads the icon straight from the site, so the backend never
 * fetches anything. A failure falls back to the initials block.
 */
export function faviconOf(url: string): string {
  try {
    return `${new URL(url).origin}/favicon.ico`;
  } catch {
    return "";
  }
}

export function initialsOf(title: string): string {
  const text = title.trim();
  if (!text) return "?";
  const first = [...text][0] ?? "?";
  if (/[㐀-鿿]/.test(first)) return first;
  const words = text.split(/[\s._-]+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return first.toUpperCase();
}

export function foldersOf(items: Bookmark[]): string[] {
  return [...new Set(items.map((item) => item.folder).filter((name): name is string => !!name))].sort(
    (a, b) => a.localeCompare(b, "zh"),
  );
}

export function filterBookmarks(
  items: Bookmark[],
  search: string,
  folder: FolderFilter,
): Bookmark[] {
  const keyword = search.trim().toLowerCase();
  return items.filter((item) => {
    if (folder !== undefined && (item.folder ?? "") !== folder) return false;
    if (!keyword) return true;
    return (
      item.title.toLowerCase().includes(keyword) ||
      item.url.toLowerCase().includes(keyword) ||
      item.note.toLowerCase().includes(keyword)
    );
  });
}

export function groupBookmarks(items: Bookmark[]): BookmarkGroup[] {
  const groups = new Map<string, BookmarkGroup>();
  for (const item of items) {
    const key = item.folder ?? "";
    const existing = groups.get(key);
    if (existing) existing.items.push(item);
    else groups.set(key, { folder: item.folder, items: [item] });
  }
  // Ungrouped rows stay last so named folders read top-down.
  return [...groups.values()].sort((a, b) => {
    if (a.folder === null) return 1;
    if (b.folder === null) return -1;
    return a.folder.localeCompare(b.folder, "zh");
  });
}

import { describe, expect, it } from "vitest";
import type { Show } from "../src/types";
import {
  filterShows,
  groupShowsByType,
  normalizeShowPayload,
  showAdvanceDisabled,
  showMetadataPatch,
  showProgressPercent,
} from "../src/features/shows/domain";

const makeShow = (overrides: Partial<Show> = {}): Show => ({
  id: 1,
  title: "葬送的芙莉莲",
  media_type: "anime",
  status: "watching",
  progress: 6,
  total: 12,
  score: 9,
  notes: "",
  update_weekday: 4,
  source: "bangumi",
  source_id: 400602,
  source_url: "https://bgm.tv/subject/400602",
  poster_path: "https://lain.bgm.tv/pic/cover/l/example.jpg",
  seasons: 1,
  air_status: "ended",
  release_year: 2023,
  completed_on: null,
  ...overrides,
});

describe("shows", () => {
  it("filters by title and status", () => {
    const shows = [makeShow(), makeShow({ id: 2, title: "沙丘", media_type: "movie", status: "planned" })];
    expect(filterShows(shows, "芙莉莲", "all")).toHaveLength(1);
    expect(filterShows(shows, "", "planned")).toEqual([shows[1]]);
  });

  it("groups in tv, anime, movie order and skips empty groups", () => {
    const groups = groupShowsByType([
      makeShow({ id: 1, media_type: "movie" }),
      makeShow({ id: 2, media_type: "anime" }),
      makeShow({ id: 3, media_type: "tv" }),
    ]);
    expect(groups.map((group) => group.type)).toEqual(["tv", "anime", "movie"]);
  });

  it("calculates bounded progress percentages", () => {
    expect(showProgressPercent({ progress: 6, total: 12 })).toBe(50);
    expect(showProgressPercent({ progress: 20, total: 12 })).toBe(100);
    expect(showProgressPercent({ progress: 3, total: null })).toBe(0);
  });

  it("disables advance when busy or complete", () => {
    expect(showAdvanceDisabled({ progress: 3, total: 12 }, false)).toBe(false);
    expect(showAdvanceDisabled({ progress: 12, total: 12 }, false)).toBe(true);
    expect(showAdvanceDisabled({ progress: 3, total: 12 }, true)).toBe(true);
  });

  it("normalizes optional values and rejects progress beyond total", () => {
    const draft = {
      title: "作品",
      notes: "",
      media_type: "tv" as const,
      status: "watching" as const,
      progress: "3",
      total: "12",
      score: "",
      update_weekday: "",
      source: "" as const,
      source_id: "",
      source_url: "",
      poster_path: "",
      seasons: "",
      air_status: "" as const,
      release_year: "",
      completed_on: "",
    };
    const result = normalizeShowPayload(draft);
    expect(result.error).toBeNull();
    if (result.data) {
      expect(result.data.progress).toBe(3);
      expect(result.data.total).toBe(12);
      expect(result.data.score).toBeNull();
      expect(result.data.source).toBeNull();
    }
    expect(normalizeShowPayload({ ...draft, progress: "13" }).error).toBe("已看进度不能大于总集数");
  });

  it("maps metadata without overwriting personal viewing fields", () => {
    const patch = showMetadataPatch({
      source: "tmdb",
      source_id: 42,
      source_url: "https://www.themoviedb.org/tv/42",
      title: "作品标题",
      original_title: "Original",
      air_date: "2024-01-01",
      release_year: 2024,
      total_episodes: 16,
      platform: "Netflix",
      image: "https://image.example/poster.jpg",
      seasons: 2,
      air_status: "ended",
    });
    expect(patch).toEqual({
      title: "作品标题",
      total: 16,
      source: "tmdb",
      source_id: 42,
      source_url: "https://www.themoviedb.org/tv/42",
      poster_path: "https://image.example/poster.jpg",
      seasons: 2,
      air_status: "ended",
      release_year: 2024,
    });
    expect(patch).not.toHaveProperty("status");
    expect(patch).not.toHaveProperty("progress");
    expect(patch).not.toHaveProperty("score");
    expect(patch).not.toHaveProperty("notes");
    expect(patch).not.toHaveProperty("completed_on");
  });
});

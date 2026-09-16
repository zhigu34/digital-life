import { describe, expect, it } from "vitest";
import type { Show } from "../src/types";
import {
  filterShows,
  normalizeShowPayload,
  showAdvanceDisabled,
  showMetadataPatch,
  showProgressPercent,
} from "../src/shows";

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
  poster_path: "https://lain.bgm.tv/pic/cover/l/example.jpg",
  seasons: 1,
  air_status: "ended",
  ...overrides,
});

describe("shows helpers", () => {
  it("filters by title case-insensitively and by status", () => {
    const shows = [
      makeShow(),
      makeShow({ id: 2, title: "Breaking Bad", status: "completed" }),
    ];

    expect(filterShows(shows, "breaking", "all").map((item) => item.id)).toEqual([2]);
    expect(filterShows(shows, "BAD", "completed").map((item) => item.id)).toEqual([2]);
    expect(filterShows(shows, "", "watching").map((item) => item.id)).toEqual([1]);
  });

  it("bounds the rendered progress percentage", () => {
    expect(showProgressPercent(makeShow())).toBe(50);
    expect(showProgressPercent(makeShow({ progress: 20 }))).toBe(100);
    expect(showProgressPercent(makeShow({ progress: 0, total: null }))).toBe(0);
  });

  it("disables advance only while busy or at the known total", () => {
    expect(showAdvanceDisabled(makeShow({ progress: 11 }), false)).toBe(false);
    expect(showAdvanceDisabled(makeShow({ progress: 12 }), false)).toBe(true);
    expect(showAdvanceDisabled(makeShow({ progress: 100, total: null }), false)).toBe(false);
    expect(showAdvanceDisabled(makeShow(), true)).toBe(true);
  });

  it("normalizes a form draft to the existing show API payload", () => {
    const result = normalizeShowPayload({
      id: 42,
      title: "测试作品",
      notes: "备注",
      media_type: "tv",
      status: "watching",
      progress: "3",
      total: "12",
      score: "8",
      update_weekday: "4",
      source: "tmdb",
      source_id: "1399",
      poster_path: "",
      seasons: "2",
      air_status: "ended",
    });

    expect(result.error).toBeNull();
    expect(result.data).toEqual({
      title: "测试作品",
      notes: "备注",
      media_type: "tv",
      status: "watching",
      progress: 3,
      total: 12,
      score: 8,
      update_weekday: 4,
      source: "tmdb",
      source_id: 1399,
      poster_path: null,
      seasons: 2,
      air_status: "ended",
    });
  });

  it("rejects a watched count above the known total", () => {
    const result = normalizeShowPayload({
      title: "测试作品",
      notes: "",
      media_type: "anime",
      status: "watching",
      progress: "13",
      total: "12",
      score: "",
      update_weekday: "",
      source: "",
      source_id: "",
      poster_path: "",
      seasons: "",
      air_status: "",
    });

    expect(result.data).toBeNull();
    expect(result.error).toBe("已看进度不能大于总集数");
  });

  it("maps a metadata candidate to the existing show form fields", () => {
    expect(
      showMetadataPatch({
        source: "tmdb",
        source_id: 1399,
        title: "权力的游戏",
        original_title: "Game of Thrones",
        air_date: "2011-04-17",
        total_episodes: 73,
        platform: "TV",
        image: "https://image.tmdb.org/t/p/w500/example.jpg",
        seasons: 8,
        air_status: "ended",
      }),
    ).toEqual({
      title: "权力的游戏",
      total: 73,
      source: "tmdb",
      source_id: 1399,
      poster_path: "https://image.tmdb.org/t/p/w500/example.jpg",
      seasons: 8,
      air_status: "ended",
    });
  });
});

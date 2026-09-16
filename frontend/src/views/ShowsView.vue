<script setup lang="ts">
import { computed, ref } from "vue";
import type { Show, Stats } from "../types";
import type { ShowFilter } from "../shows";
import { filterShows } from "../shows";
import { labels } from "../domain";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";
import ShowCard from "../components/ShowCard.vue";

const props = defineProps<{
  shows: Show[];
  stats: Stats | null;
  busy: boolean;
}>();

const emit = defineEmits<{
  create: [];
  edit: [item: Show];
  action: [id: number, action: "advance"];
}>();

const search = ref("");
const filter = ref<ShowFilter>("all");
const tabs: ShowFilter[] = ["all", "watching", "planned", "completed", "paused"];
const filtered = computed(() => filterShows(props.shows, search.value, filter.value));
</script>

<template>
  <section class="page collection-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">A GOOD STORY AWAITS</span>
        <h1>
          追剧片单<span class="heading-count">{{ shows.length }}</span>
        </h1>
        <p>收藏想看的故事，记住每一次看到哪里。</p>
      </div>
      <button class="button primary" @click="emit('create')">
        <AppIcon name="plus" :size="18" />添加作品
      </button>
    </header>

    <section v-if="stats && shows.length" class="shows-stats" aria-label="追剧统计">
      <div
        v-for="[value, label] in [
          [stats.shows.watching, '在看'],
          [stats.shows.planned, '想看'],
          [stats.shows.completed, '已看完'],
          [stats.shows.paused, '暂搁'],
        ]"
        :key="label"
        class="summary-card"
      >
        <span>{{ label }}</span><strong>{{ value }}</strong>
      </div>
      <div class="summary-card">
        <span>累计看完</span>
        <strong>{{ stats.shows.episodes_watched }}<small>集</small></strong>
      </div>
    </section>

    <div class="collection-toolbar">
      <div class="tabs" aria-label="状态筛选">
        <button
          v-for="tab in tabs"
          :key="tab"
          :class="{ active: filter === tab }"
          @click="filter = tab"
        >
          {{ tab === "all" ? "全部" : labels[tab] }}
        </button>
      </div>
      <label class="search-box">
        <AppIcon name="search" :size="17" />
        <input v-model="search" aria-label="搜索记录" placeholder="搜索记录…" />
      </label>
    </div>

    <EmptyState
      v-if="!shows.length"
      icon="shows"
      title="下一段好故事，等你开启"
      description="添加一部想看的电影、剧集或动漫，慢慢享受。"
      action="添加作品"
      @action="emit('create')"
    />
    <EmptyState
      v-else-if="!filtered.length"
      icon="search"
      title="没有找到对应记录"
      description="试试其他关键词，或切换状态筛选。"
    />
    <div v-else class="record-list card-grid has-shows">
      <ShowCard
        v-for="item in filtered"
        :key="item.id"
        :item="item"
        :busy="busy"
        @edit="emit('edit', $event)"
        @advance="emit('action', $event, 'advance')"
      />
    </div>

    <p v-if="shows.length" class="page-footnote">一点一滴，都是生活的痕迹。</p>
  </section>
</template>

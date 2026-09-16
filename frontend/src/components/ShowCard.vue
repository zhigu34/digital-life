<script setup lang="ts">
import { computed } from "vue";
import type { Show } from "../types";
import { labels } from "../domain";
import { showAdvanceDisabled, showProgressPercent } from "../shows";
import AppIcon from "./AppIcon.vue";

const props = defineProps<{
  item: Show;
  busy: boolean;
}>();

const emit = defineEmits<{
  edit: [item: Show];
  advance: [id: number];
}>();

const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const isSeries = computed(() => props.item.media_type !== "movie");
</script>

<template>
  <article class="record-card show-card" :class="`show-card-${item.media_type}`">
    <button
      type="button"
      class="show-cover"
      :class="item.media_type"
      :aria-label="`编辑 ${item.title}`"
      @click="emit('edit', item)"
    >
      <img
        v-if="item.poster_path"
        :src="`/api/shows/${item.id}/poster`"
        :alt="item.title"
        loading="lazy"
      />
      <AppIcon v-else name="shows" :size="30" />
      <span v-if="item.score" class="show-score">★ {{ item.score }}</span>
    </button>
    <div class="record-body show-card-body">
      <div class="show-card-heading">
        <div>
          <h3>
            <a
              v-if="item.source_url"
              class="show-title-link"
              :href="item.source_url"
              target="_blank"
              rel="noopener noreferrer"
            >{{ item.title }}</a>
            <span v-else>{{ item.title }}</span>
          </h3>
          <div class="record-meta show-primary-meta">
            <span :class="['tag', item.status]">{{ labels[item.status] }}</span>
            <span class="show-kind">{{ labels[item.media_type] }}</span>
            <span v-if="item.release_year">{{ item.release_year }}</span>
          </div>
        </div>
      </div>

      <div class="show-detail-line">
        <template v-if="isSeries">
          <span v-if="item.seasons">{{ item.seasons }} 季</span>
          <span v-if="item.update_weekday !== null">{{ weekdays[item.update_weekday] }}更新</span>
          <span v-if="item.air_status">{{ labels[item.air_status] }}</span>
        </template>
        <template v-else>
          <span v-if="item.air_status">{{ labels[item.air_status] }}</span>
          <span v-if="item.completed_on">看完于 {{ item.completed_on }}</span>
        </template>
      </div>

      <p v-if="item.notes" class="record-notes show-card-notes">{{ item.notes }}</p>

      <template v-if="isSeries">
        <div class="show-progress show-progress-strong">
          <span>
            已看 <strong>{{ item.progress }}</strong>
            <span class="muted"> / {{ item.total ?? "—" }} 集</span>
          </span>
          <button
            class="text-button show-advance"
            aria-label="看完一集"
            :disabled="showAdvanceDisabled(item, busy)"
            @click="emit('advance', item.id)"
          >
            <AppIcon name="plus" :size="15" />+1 集
          </button>
        </div>
        <div class="progress-track">
          <span :style="{ width: `${showProgressPercent(item)}%` }"></span>
        </div>
        <span v-if="item.completed_on" class="show-completed-date">看完于 {{ item.completed_on }}</span>
      </template>
    </div>
  </article>
</template>

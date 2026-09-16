<script setup lang="ts">
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
</script>

<template>
  <article class="record-card show-card">
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
    <div class="record-body">
      <div class="record-meta">
        <span :class="['tag', item.status]">{{ labels[item.status] }}</span>
        <span v-if="item.seasons">{{ item.seasons }} 季</span>
        <span v-if="item.air_status" :class="['tag', item.air_status]">
          {{ labels[item.air_status] }}
        </span>
        <span v-if="item.update_weekday !== null">
          {{ weekdays[item.update_weekday] }}更新
        </span>
        <span class="show-kind">{{ labels[item.media_type] }}</span>
      </div>
      <h3>{{ item.title }}</h3>
      <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
      <div class="show-progress">
        <span>
          已看 {{ item.progress }}
          <span class="muted">/ {{ item.total ?? "—" }} 集</span>
        </span>
        <button
          class="text-button"
          :disabled="showAdvanceDisabled(item, busy)"
          @click="emit('advance', item.id)"
        >
          <AppIcon name="plus" :size="15" />看完一集
        </button>
      </div>
      <div class="progress-track">
        <span :style="{ width: `${showProgressPercent(item)}%` }"></span>
      </div>
    </div>
  </article>
</template>

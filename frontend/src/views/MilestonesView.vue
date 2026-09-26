<script setup lang="ts">
import { computed, ref } from "vue";
import type { Milestone, RecordItem } from "../types";
import { countdown } from "../domain";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";

const props = defineProps<{
  records: { milestones: Milestone[] };
  today: string;
}>();
const emit = defineEmits<{ create: []; edit: [item: RecordItem]; remove: [item: RecordItem] }>();
const search = ref("");
const filtered = computed(() =>
  props.records.milestones.filter((item) =>
    item.title.toLowerCase().includes(search.value.toLowerCase()),
  ),
);
</script>

<template>
  <section class="page collection-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">MOMENTS THAT MATTER</span>
        <h1>
          重要日子<span class="heading-count">{{ records.milestones.length }}</span>
        </h1>
        <p>平凡的日期，也可以装着特别的意义。</p>
      </div>
      <button class="button primary" @click="emit('create')">
        <AppIcon name="plus" :size="18" />添加日子
      </button>
    </header>

    <div class="collection-toolbar">
      <span class="muted small">{{ filtered.length }} 条记录 · 留意每一点日常</span
      ><label class="search-box"
        ><AppIcon name="search" :size="17" /><input
          v-model="search"
          aria-label="搜索记录"
          placeholder="搜索记录…"
      /></label>
    </div>

    <EmptyState
      v-if="!records.milestones.length"
      icon="milestones"
      title="总有一些日子值得记住"
      description="生日、周年、旅行出发日，把期待留在这里。"
      action="添加日子"
      @action="emit('create')"
    /><EmptyState
      v-else-if="!filtered.length"
      icon="search"
      title="没有找到对应记录"
      description="试试其他关键词。"
    />

    <div v-else class="record-list card-grid">
      <article v-for="item in filtered" :key="item.id" class="record-card">
        <div class="milestone-top">
          <span class="record-symbol"><AppIcon name="milestones" /></span
          ><span class="tag">{{ item.repeats_yearly ? "每年纪念" : "特别的一天" }}</span>
        </div>
        <div class="record-body">
          <h3>{{ item.title }}</h3>
          <div class="countdown-number">
            <strong>{{ Math.abs(countdown(item.date, item.repeats_yearly, today)) }}</strong
            ><span>{{
              countdown(item.date, item.repeats_yearly, today) < 0
                ? "天已经过去"
                : countdown(item.date, item.repeats_yearly, today) === 0
                  ? "就是今天"
                  : "天后到来"
            }}</span>
          </div>
          <p class="muted small">{{ item.date.replaceAll("-", ".") }}</p>
          <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
        </div>
        <div class="record-actions">
          <button class="icon-button" :aria-label="`编辑 ${item.title}`" @click="emit('edit', item)">
            <AppIcon name="edit" :size="16" /></button
          ><button
            class="icon-button danger-hover"
            :aria-label="`删除 ${item.title}`"
            @click="emit('remove', item)"
          >
            <AppIcon name="delete" :size="16" />
          </button>
        </div>
      </article>
    </div>
    <p v-if="records.milestones.length" class="page-footnote">
      一点一滴，都是生活的痕迹。
    </p>
  </section>
</template>

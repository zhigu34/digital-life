<script setup lang="ts">
import { computed } from "vue";
import AppIcon from "../../components/AppIcon.vue";
import type { GroupItem, RepeatUnit, TaskGroup } from "../../types";
import {
  currentSlot,
  gridCount,
  hitRate,
  repeatLabel,
  slotsFor,
  streak,
  streakUnit,
} from "./periods";

const props = defineProps<{ group: TaskGroup; today: string; busy: boolean }>();
const emit = defineEmits<{
  toggle: [item: GroupItem];
  open: [item: GroupItem];
  addItem: [];
  edit: [];
  archive: [];
  removeItem: [item: GroupItem];
  remove: [];
}>();

const UNITS: RepeatUnit[] = ["day", "week", "month"];
const UNIT_WORD: Record<RepeatUnit, string> = { day: "每天", week: "每周", month: "每月" };

const summary = computed(() => {
  const parts = UNITS.map((unit) => {
    const count = props.group.items.filter((item) => item.repeat_unit === unit).length;
    return count ? `${UNIT_WORD[unit]} ${count} 项` : "";
  }).filter(Boolean);
  return parts.join(" · ");
});
const progress = computed(() => {
  const expected = props.group.items.filter(
    (item) => currentSlot(item, props.today, props.group.archived_on).state !== "before",
  );
  const satisfied = expected.filter(
    (item) => currentSlot(item, props.today, props.group.archived_on).state === "done",
  );
  return { satisfied: satisfied.length, expected: expected.length };
});

function slots(item: GroupItem) {
  return slotsFor(item, props.today, gridCount(item.repeat_unit), props.group.archived_on);
}
function isCurrent(slot: { start: string; end: string }) {
  return slot.start <= props.today && props.today <= slot.end;
}
function doneToday(item: GroupItem) {
  return item.recent_days.includes(props.today);
}
function periodWord(item: GroupItem) {
  if (item.repeat_unit === "week") return "本周";
  return item.repeat_unit === "month" ? "本月" : "今天";
}
function statusText(item: GroupItem) {
  const slot = currentSlot(item, props.today, props.group.archived_on);
  if (slot.state === "done") {
    return item.repeat_unit === "day" ? "今天已完成" : `${periodWord(item)}已完成 ${slot.count} 次`;
  }
  if (slot.state === "before") return "已归档";
  return item.repeat_unit === "day" ? "今天还没打卡" : `${periodWord(item)}还没完成`;
}
function streakText(item: GroupItem) {
  const value = streak(item, props.today, props.group.archived_on);
  return value ? `连续 ${value} ${streakUnit(item.repeat_unit)}` : "还没有连续记录";
}
function rateText(item: GroupItem) {
  const { done, expected } = hitRate(item, props.today, props.group.archived_on);
  return `${done}/${expected} 个周期达标`;
}
function slotLabel(item: GroupItem, slot: { label: string; state: string; count: number }) {
  const state = { done: "已达标", missed: "未达标", pending: "进行中", before: "不在计划内" }[
    slot.state
  ];
  return `${slot.label} ${state}${slot.count > 1 ? `，完成 ${slot.count} 次` : ""}`;
}
function askRemove(item: GroupItem) {
  if (window.confirm(`确定删除“${item.title}”及其全部打卡记录？删除后无法恢复。`)) {
    emit("removeItem", item);
  }
}
</script>

<template>
  <article class="group-card" :class="{ archived: group.archived }">
    <header class="group-head">
      <div class="group-head-main">
        <h3>
          {{ group.title }}<span v-if="group.archived" class="tag">已归档</span>
        </h3>
        <p class="group-sub">{{ summary }}</p>
      </div>
      <span class="progress-pill" :class="{ lagging: progress.satisfied < progress.expected }">
        本期 {{ progress.satisfied }}/{{ progress.expected }} 项达标
      </span>
      <div class="record-actions">
        <button
          class="icon-button"
          :aria-label="`为 ${group.title} 添加打卡项`"
          :disabled="busy || group.archived"
          @click="emit('addItem')"
        >
          <AppIcon name="plus" :size="16" />
        </button>
        <button class="text-button" :disabled="busy" @click="emit('archive')">
          {{ group.archived ? "恢复" : "归档" }}
        </button>
        <button class="icon-button" :aria-label="`编辑 ${group.title}`" :disabled="busy" @click="emit('edit')">
          <AppIcon name="edit" :size="16" />
        </button>
        <button
          class="icon-button danger-hover"
          :aria-label="`删除 ${group.title}`"
          :disabled="busy"
          @click="emit('remove')"
        >
          <AppIcon name="delete" :size="16" />
        </button>
      </div>
    </header>

    <div v-for="item in group.items" :key="item.id" class="item-row">
      <button
        class="checkin-hit"
        :class="{ done: doneToday(item), inactive: group.archived }"
        :aria-label="`${doneToday(item) ? '撤销打卡' : '打卡'} ${item.title}`"
        :disabled="busy || group.archived"
        @click="emit('toggle', item)"
      >
        <AppIcon v-if="doneToday(item)" name="check" :size="22" />
      </button>
      <div class="checkin-body">
        <div class="checkin-title-row">
          <h3>{{ item.title }}</h3>
          <span :class="['tag', `repeat-${item.repeat_unit}`]">{{ repeatLabel(item.repeat_unit) }}</span>
        </div>
        <p class="stat-line">
          <strong>{{ streakText(item) }}</strong> · 累计 {{ item.total_count }} 次 ·
          {{ statusText(item) }}
        </p>
        <div class="period-grid">
          <button
            v-for="slot in slots(item)"
            :key="slot.start"
            class="period-cell"
            :class="[slot.state, { current: isCurrent(slot) }]"
            type="button"
            :aria-label="slotLabel(item, slot)"
            @click="emit('open', item)"
          >
            {{ slot.cell }}<span v-if="slot.count > 1" class="mult">{{ slot.count }}</span>
          </button>
        </div>
        <p class="muted small period-note">{{ rateText(item) }}</p>
      </div>
      <div class="item-actions">
        <button
          class="icon-button"
          :aria-label="`${item.title} 的历史明细`"
          :disabled="busy"
          @click="emit('open', item)"
        >
          <AppIcon name="history" :size="16" />
        </button>
        <button
          class="icon-button danger-hover"
          :aria-label="`删除 ${item.title}`"
          :disabled="busy"
          @click="askRemove(item)"
        >
          <AppIcon name="delete" :size="16" />
        </button>
      </div>
    </div>
  </article>
</template>

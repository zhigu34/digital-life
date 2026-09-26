<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";
import type { GroupItem, TaskCompletion, TaskGroup } from "../../types";
import { listCompletions } from "./api";
import { gridCount, periodStart, repeatLabel, slotsFor } from "./periods";

const props = defineProps<{
  group: TaskGroup;
  item: GroupItem;
  today: string;
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{
  close: [];
  check: [payload: { on: string; note: string }];
  undo: [on: string];
  edit: [];
  remove: [];
  error: [error: unknown];
}>();

const slots = computed(() =>
  slotsFor(props.item, props.today, gridCount(props.item.repeat_unit), props.group.archived_on),
);
const selected = ref(slots.value.at(-1)?.start ?? props.today);
const rows = ref<TaskCompletion[]>([]);
const loading = ref(false);
const makeup = reactive({ on: props.today, note: "" });

const current = computed(
  () => slots.value.find((slot) => slot.start === selected.value) ?? slots.value.at(-1),
);

async function load() {
  const slot = current.value;
  if (!slot) return;
  loading.value = true;
  try {
    rows.value = await listCompletions(props.item.group_id, props.item.id, slot.start, slot.end);
  } catch (e) {
    rows.value = [];
    emit("error", e);
  } finally {
    loading.value = false;
  }
}

// A new completion (or an undo) reaches this dialog through the refreshed item,
// so watching the days keeps the list in step without a second cache.
watch(
  [selected, () => props.item.id, () => props.item.recent_days.join(",")],
  () => void load(),
  { immediate: true },
);

function submit() {
  emit("check", { on: makeup.on, note: makeup.note });
  makeup.note = "";
  // Follow the entry into its own period, otherwise a makeup dated outside the
  // selected one would be saved and then appear to have vanished.
  const target = periodStart(makeup.on, props.item.repeat_unit);
  if (slots.value.some((slot) => slot.start === target)) selected.value = target;
}
</script>

<template>
  <ModalDialog
    :title="item.title"
    :subtitle="`${group.title} · ${repeatLabel(item.repeat_unit)} · 一个周期内记几次都算达标`"
    @close="emit('close')"
  >
    <div class="period-picker" aria-label="选择周期">
      <button
        v-for="slot in slots"
        :key="slot.start"
        type="button"
        class="period-cell"
        :class="[slot.state, { active: slot.start === selected }]"
        :aria-label="slot.label"
        @click="selected = slot.start"
      >
        {{ slot.cell }}<span v-if="slot.count > 1" class="mult">{{ slot.count }}</span>
      </button>
    </div>
    <p class="muted small period-picker-label">{{ current?.label }}</p>

    <form class="record-form" @submit.prevent="submit">
      <div class="form-grid">
        <label>补记日期<input v-model="makeup.on" type="date" :max="today" required /></label>
      </div>
      <label
        >当天备注 <span class="optional">选填</span
        ><input v-model="makeup.note" maxlength="4000" placeholder="例如：练了背"
      /></label>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <footer class="modal-actions">
        <button type="button" class="button secondary" @click="emit('close')">完成</button
        ><button class="button primary" :disabled="busy">
          {{ busy ? "保存中…" : "记一笔" }}
        </button>
      </footer>
    </form>

    <div class="checkin-log-list" aria-label="这个周期的打卡记录">
      <p v-if="loading" class="muted small">正在加载…</p>
      <p v-else-if="!rows.length" class="muted small">这个周期还没有记录。</p>
      <div v-for="row in rows" :key="row.id" class="checkin-log-row">
        <strong>{{ row.completed_on }}</strong>
        <span class="muted small">{{ row.note || "—" }}</span>
        <button
          class="icon-button danger-hover"
          :aria-label="`删除 ${row.completed_on} 的记录`"
          :disabled="busy"
          @click="emit('undo', row.completed_on)"
        >
          <AppIcon name="delete" :size="15" />
        </button>
      </div>
    </div>

    <footer class="modal-actions">
      <button type="button" class="button secondary" :disabled="busy" @click="emit('edit')">
        <AppIcon name="edit" :size="15" />编辑该打卡项
      </button>
      <button
        type="button"
        class="button danger-ghost"
        :disabled="busy"
        @click="emit('remove')"
      >
        <AppIcon name="delete" :size="15" />删除该打卡项
      </button>
    </footer>
  </ModalDialog>
</template>

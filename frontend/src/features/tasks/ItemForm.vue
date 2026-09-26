<script setup lang="ts">
import { reactive } from "vue";
import ModalDialog from "../../components/ModalDialog.vue";
import type { GroupItem, RepeatUnit } from "../../types";

const props = defineProps<{
  item?: GroupItem;
  groupTitle: string;
  today: string;
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{ close: []; save: [payload: Record<string, unknown>] }>();

const editing = !!props.item;
const form = reactive({
  title: props.item?.title ?? "",
  repeat_unit: (props.item?.repeat_unit ?? "day") as RepeatUnit,
  start_date: props.item?.start_date ?? props.today,
});
const units: { value: RepeatUnit; label: string }[] = [
  { value: "day", label: "每天" },
  { value: "week", label: "本周内完成" },
  { value: "month", label: "本月内完成" },
];
</script>

<template>
  <ModalDialog
    :title="editing ? `编辑打卡项` : `为 ${groupTitle} 添加打卡项`"
    subtitle="每周、每月都是周期内完成即可，不必固定在星期几或几号。"
    @close="emit('close')"
  >
    <form class="record-form" @submit.prevent="emit('save', { ...form })">
      <label
        >打卡项<input
          v-model="form.title"
          required
          minlength="1"
          maxlength="120"
          placeholder="例如：力量训练"
      /></label>
      <div class="form-grid">
        <label class="select-field"
          >周期<select v-model="form.repeat_unit" aria-label="打卡周期">
            <option v-for="unit in units" :key="unit.value" :value="unit.value">
              {{ unit.label }}
            </option>
          </select></label
        >
        <label>开始日期<input v-model="form.start_date" type="date" required /></label>
      </div>
      <p class="muted small">
        从开始日期起才会计算"没完成"；在这之前的周期不会被记成漏做。
      </p>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <footer class="modal-actions">
        <button type="button" class="button secondary" @click="emit('close')">取消</button
        ><button class="button primary" :disabled="busy">
          {{ busy ? "保存中…" : "保存" }}
        </button>
      </footer>
    </form>
  </ModalDialog>
</template>

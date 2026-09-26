<script setup lang="ts">
import { reactive, ref } from "vue";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";
import type { RepeatUnit, TaskGroup } from "../../types";

const props = defineProps<{ group?: TaskGroup; busy: boolean; error: string }>();
const emit = defineEmits<{ close: []; save: [payload: Record<string, unknown>] }>();

const editing = !!props.group;
const form = reactive({ title: props.group?.title ?? "", notes: props.group?.notes ?? "" });
const rows = ref<{ title: string; repeat_unit: RepeatUnit }[]>([
  { title: "", repeat_unit: "day" },
]);
const units: { value: RepeatUnit; label: string }[] = [
  { value: "day", label: "每天" },
  { value: "week", label: "本周内完成" },
  { value: "month", label: "本月内完成" },
];

function submit() {
  if (editing) {
    emit("save", { title: form.title, notes: form.notes });
    return;
  }
  // Blank rows are simply dropped: a group is valid once one item is named.
  const items = rows.value
    .map((row) => ({ title: row.title.trim(), repeat_unit: row.repeat_unit }))
    .filter((row) => row.title);
  if (!items.length) return;
  emit("save", { title: form.title, notes: form.notes, items });
}
</script>

<template>
  <ModalDialog
    :title="editing ? `编辑 ${group?.title}` : '添加长期任务'"
    :subtitle="
      editing
        ? '改名字或备注不会影响已经记录下来的打卡。'
        : '一个分组可以同时放每天、每周、每月的打卡项。'
    "
    @close="emit('close')"
  >
    <form class="record-form" @submit.prevent="submit">
      <label
        >分组名称<input
          v-model="form.title"
          required
          minlength="1"
          maxlength="120"
          placeholder="例如：健身计划"
      /></label>
      <label
        >备注 <span class="optional">选填</span
        ><textarea v-model="form.notes" rows="2" maxlength="4000"></textarea>
      </label>
      <template v-if="!editing">
        <div v-for="(row, index) in rows" :key="index" class="item-draft">
          <label
            >打卡项<input
              v-model="row.title"
              maxlength="120"
              placeholder="例如：跑步 30 分钟"
          /></label>
          <label class="select-field"
            >周期<select v-model="row.repeat_unit" :aria-label="`第 ${index + 1} 个打卡项的周期`">
              <option v-for="unit in units" :key="unit.value" :value="unit.value">
                {{ unit.label }}
              </option>
            </select></label
          >
          <button
            v-if="rows.length > 1"
            type="button"
            class="icon-button danger-hover"
            :aria-label="`删除第 ${index + 1} 个打卡项`"
            @click="rows.splice(index, 1)"
          >
            <AppIcon name="delete" :size="15" />
          </button>
        </div>
        <button type="button" class="text-button" @click="rows.push({ title: '', repeat_unit: 'day' })">
          <AppIcon name="plus" :size="15" />再加一项
        </button>
      </template>
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

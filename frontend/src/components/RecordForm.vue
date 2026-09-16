<script setup lang="ts">
import { reactive, ref } from "vue";
import type { Collection, RecordItem } from "../types";
import AppIcon from "./AppIcon.vue";
import ModalDialog from "./ModalDialog.vue";

type GenericCollection = Exclude<Collection, "shows">;

const props = defineProps<{
  collection: GenericCollection;
  item?: RecordItem;
  today: string;
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{
  close: [];
  save: [data: Record<string, unknown>];
  remove: [item: RecordItem];
}>();
const titles: Record<GenericCollection, string> = {
  tasks: "待办",
  expenses: "周期费用",
  milestones: "重要日子",
};
const defaults: Record<GenericCollection, Record<string, any>> = {
  tasks: { title: "", notes: "", status: "todo", due_date: "", priority: "normal" },
  expenses: {
    title: "",
    notes: "",
    amount_cents: 0,
    currency: "CNY",
    period_months: 1,
    next_due: props.today,
    anchor_day: Number(props.today.slice(-2)),
    active: true,
  },
  milestones: { title: "", notes: "", date: props.today, repeats_yearly: false },
};
const placeholders: Record<GenericCollection, string> = {
  tasks: "例如：读完书架上的那本书",
  expenses: "例如：云存储订阅",
  milestones: "例如：第一次出发的日子",
};
const form = reactive<Record<string, any>>({ ...defaults[props.collection], ...props.item });
const amount = ref(
  props.item && "amount_cents" in props.item
    ? (props.item.amount_cents / 100).toFixed(2)
    : "",
);

function save() {
  const data = { ...form };
  delete data.id;
  delete data.created_at;
  if (props.collection === "tasks") data.due_date = data.due_date || null;
  if (props.collection === "expenses") {
    data.amount_cents = Math.round(Number(amount.value) * 100);
    data.period_months = Number(data.period_months);
    data.anchor_day = Number(data.anchor_day);
  }
  emit("save", data);
}
</script>

<template>
  <ModalDialog
    :title="`${item ? '编辑' : '添加'}${titles[collection]}`"
    subtitle="给生活中的这件事，留一个位置。"
    @close="emit('close')"
  >
    <form class="record-form" @submit.prevent="save">
      <label>名称<input v-model="form.title" required :maxlength="collection === 'tasks' ? 160 : 120" autofocus :placeholder="placeholders[collection]" /></label>

      <template v-if="collection === 'tasks'">
        <div class="form-grid">
          <label>状态<select v-model="form.status"><option value="todo">待办</option><option value="doing">进行中</option><option value="waiting">等待中</option><option value="done">已完成</option></select></label>
          <label>优先级<select v-model="form.priority"><option value="low">低优先</option><option value="normal">普通</option><option value="high">高优先</option></select></label>
        </div>
        <label>截止日期 <span class="optional">选填</span><input v-model="form.due_date" type="date" /></label>
      </template>

      <template v-if="collection === 'expenses'">
        <div class="form-grid">
          <label>每期金额<input v-model="amount" type="number" required min="0.01" max="1000000" step="0.01" placeholder="0.00" /></label>
          <label>币种<select v-model="form.currency"><option v-for="currency in ['CNY', 'USD', 'EUR', 'JPY', 'HKD']" :key="currency">{{ currency }}</option></select></label>
          <label>付费周期<select v-model="form.period_months"><option :value="1">每月</option><option :value="3">每季度</option><option :value="12">每年</option></select></label>
          <label>下次应付<input v-model="form.next_due" type="date" required @change="form.anchor_day = Number(form.next_due.slice(-2))" /></label>
        </div>
        <label>固定扣费日 <span class="optional">短月自动取月底</span><input v-model="form.anchor_day" type="number" min="1" max="31" required /></label>
        <label class="checkbox-label"><input v-model="form.active" type="checkbox" />正在使用（计入费用统计）</label>
      </template>

      <template v-if="collection === 'milestones'">
        <label>日期<input v-model="form.date" type="date" required /></label>
        <label class="checkbox-label"><input v-model="form.repeats_yearly" type="checkbox" />每年纪念这个日子</label>
        <p class="field-hint">2 月 29 日的周年，在平年按 2 月 28 日计算。</p>
      </template>

      <label>备注 <span class="optional">选填</span><textarea v-model="form.notes" rows="3" maxlength="4000" placeholder="一些想记住的小细节…"></textarea></label>
      <p v-if="error" role="alert" class="form-error">{{ error }}</p>
      <footer class="modal-actions">
        <button v-if="item" type="button" class="button danger-ghost" :disabled="busy" @click="emit('remove', item)"><AppIcon name="delete" :size="15" />删除</button>
        <button type="button" class="button secondary" :disabled="busy" @click="emit('close')">取消</button>
        <button class="button primary" :disabled="busy">{{ busy ? "保存中…" : "保存记录" }}</button>
      </footer>
    </form>
  </ModalDialog>
</template>

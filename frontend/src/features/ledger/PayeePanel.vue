<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import type { LedgerPayee } from "../../types";
import { createPayee, deletePayee, mergePayee, updatePayee } from "./api";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";

const props = defineProps<{ payees: LedgerPayee[]; busy: boolean }>();
const emit = defineEmits<{
  changed: [];
  error: [error: unknown];
  notice: [message: string];
}>();

const sorted = computed(() =>
  [...props.payees].sort((a, b) => a.name.localeCompare(b.name, "zh-CN")),
);
const editing = ref<LedgerPayee | null | undefined>(undefined);
const mergeInto = ref<Record<number, number | null>>({});
const formError = ref("");
const form = reactive({ name: "", archived: false });

function open(item?: LedgerPayee) {
  formError.value = "";
  editing.value = item ?? null;
  form.name = item?.name ?? "";
  form.archived = item?.archived ?? false;
}
function close() {
  editing.value = undefined;
  formError.value = "";
}
async function save() {
  formError.value = "";
  try {
    const item = editing.value;
    if (item) await updatePayee(item.id, { name: form.name, archived: form.archived });
    else await createPayee({ name: form.name });
    close();
    emit("changed");
    emit("notice", item ? "商户已更新" : "商户已添加");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
  }
}
async function remove(item: LedgerPayee) {
  if (!window.confirm(`确定删除商户“${item.name}”？已被流水使用时请改为归档或合并到其他商户。`)) return;
  try {
    await deletePayee(item.id);
    close();
    emit("changed");
    emit("notice", "商户已删除");
  } catch (e) {
    emit("error", e);
  }
}
async function merge(item: LedgerPayee) {
  const target = mergeInto.value[item.id];
  if (!target) return;
  const name = props.payees.find((row) => row.id === target)?.name ?? "";
  if (!window.confirm(`把“${item.name}”的流水与账单全部改挂到“${name}”，然后删除前者？`)) return;
  try {
    const result = await mergePayee(item.id, target);
    mergeInto.value = {};
    emit("changed");
    emit("notice", `已合并 ${result.entries} 笔流水、${result.expenses} 条账单`);
  } catch (e) {
    emit("error", e);
  }
}
</script>

<template>
  <section class="manage-block">
    <header class="manage-heading">
      <div><h2>商户</h2><p class="summary-note">只记录「钱花给谁」。名字存前会去掉首尾空格，忽略大小写判重；记一笔时直接输入新名字即可新建。</p></div>
      <button class="button secondary" @click="open()"><AppIcon name="plus" :size="16" />添加商户</button>
    </header>

    <ul v-if="sorted.length" class="chip-list wide">
      <li v-for="item in sorted" :key="item.id" class="chip-row" :class="{ inactive: item.archived }">
        <span>{{ item.name }}<span v-if="item.archived" class="tag">已归档</span></span>
        <span class="chip-actions merge-actions">
          <select :value="mergeInto[item.id] ?? null" @change="mergeInto = { ...mergeInto, [item.id]: Number(($event.target as HTMLSelectElement).value) || null }">
            <option :value="null">合并到…</option>
            <option v-for="row in sorted" :key="row.id" :value="row.id" :disabled="row.id === item.id">{{ row.name }}</option>
          </select>
          <button class="text-button" :disabled="!mergeInto[item.id]" @click="merge(item)">合并</button>
          <button class="icon-button" :aria-label="`编辑 ${item.name}`" @click="open(item)"><AppIcon name="edit" :size="14" /></button>
          <button class="icon-button danger-hover" :aria-label="`删除 ${item.name}`" @click="remove(item)"><AppIcon name="delete" :size="14" /></button>
        </span>
      </li>
    </ul>
    <p v-else class="muted small">还没有商户。记流水时直接输入新名字，就会自动出现在这里。</p>

    <ModalDialog v-if="editing !== undefined" :title="`${editing ? '编辑' : '添加'}商户`" subtitle="商户用来回答「这钱花给谁」。" @close="close">
      <form class="record-form" @submit.prevent="save">
        <label>名称<input v-model="form.name" required maxlength="40" autofocus placeholder="例如：老张面馆" /></label>
        <label v-if="editing" class="checkbox-label"><input v-model="form.archived" type="checkbox" />归档（不在记账时选择，流水保留）</label>
        <p v-if="formError" role="alert" class="form-error">{{ formError }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="close">取消</button>
          <button class="button primary" :disabled="busy">{{ busy ? "保存中…" : "保存商户" }}</button>
        </footer>
      </form>
    </ModalDialog>
  </section>
</template>

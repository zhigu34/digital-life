<script setup lang="ts">
import { reactive, ref } from "vue";
import type { LedgerBook } from "../../types";
import { createBook, deleteBook, updateBook } from "./api";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";

defineProps<{ books: LedgerBook[]; busy: boolean }>();
const emit = defineEmits<{
  changed: [];
  error: [error: unknown];
  notice: [message: string];
  "view-entries": [bookId: number];
}>();

const editing = ref<LedgerBook | null | undefined>(undefined);
const formError = ref("");
const form = reactive({ name: "", archived: false });

function open(item?: LedgerBook) {
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
  const item = editing.value;
  const payload = { name: form.name, archived: form.archived };
  try {
    if (item) await updateBook(item.id, payload);
    else await createBook(payload);
    close();
    emit("changed");
    emit("notice", item ? "账本已更新" : "账本已添加");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
  }
}
async function remove(item: LedgerBook) {
  if (!window.confirm(`确定删除账本“${item.name}”？已有流水的账本无法删除，请改用归档。`)) return;
  try {
    await deleteBook(item.id);
    close();
    emit("changed");
    emit("notice", "账本已删除");
  } catch (e) {
    emit("error", e);
  }
}
</script>

<template>
  <section class="manage-block">
    <header class="manage-heading">
      <div>
        <h2>账本</h2>
        <p class="summary-note">账本只是流水与账单上的标签，用来归集专项开销；账户和余额始终共用一份，切账本不会改变它们。</p>
      </div>
      <button class="button secondary" @click="open()"><AppIcon name="plus" :size="16" />添加账本</button>
    </header>

    <ul v-if="books.length" class="book-chips">
      <li v-for="item in books" :key="item.id" class="book-chip" :class="{ inactive: item.archived }">
        <button class="text-button" :disabled="item.archived" @click="emit('view-entries', item.id)">{{ item.name }}<AppIcon name="chevron" :size="14" /></button>
        <span v-if="item.archived" class="tag">已归档</span>
        <button class="icon-button" :aria-label="`编辑 ${item.name}`" @click="open(item)"><AppIcon name="edit" :size="16" /></button>
        <button class="icon-button danger-hover" :aria-label="`删除 ${item.name}`" @click="remove(item)"><AppIcon name="delete" :size="16" /></button>
      </li>
    </ul>
    <p v-else class="muted small">还没有账本。为专项开销建一个，比如「装修」或「旅行」。</p>

    <ModalDialog v-if="editing !== undefined" :title="`${editing ? '编辑' : '添加'}账本`" subtitle="专项账目的名字，例如装修、旅行、考证。" @close="close">
      <form class="record-form" @submit.prevent="save">
        <label>名称<input v-model="form.name" required maxlength="20" autofocus placeholder="例如：装修" /></label>
        <label class="checkbox-label"><input v-model="form.archived" type="checkbox" />归档（不在记账时选择，流水保留）</label>
        <p v-if="formError" role="alert" class="form-error">{{ formError }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="close">取消</button>
          <button class="button primary" :disabled="busy">{{ busy ? "保存中…" : "保存账本" }}</button>
        </footer>
      </form>
    </ModalDialog>
  </section>
</template>

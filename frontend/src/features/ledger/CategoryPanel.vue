<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import type { CategoryKind, LedgerCategory } from "../../types";
import { createCategory, deleteCategory, updateCategory } from "./api";
import { categoryKindLabels } from "./ledger";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";

const props = defineProps<{ categories: LedgerCategory[]; busy: boolean }>();
const emit = defineEmits<{
  changed: [];
  error: [error: unknown];
  notice: [message: string];
}>();

const groups = computed(() =>
  (["expense", "income"] as CategoryKind[]).map((kind) => ({
    kind,
    label: categoryKindLabels[kind],
    rows: props.categories.filter((row) => row.kind === kind),
  })),
);
const editing = ref<LedgerCategory | null | undefined>(undefined);
const formError = ref("");
const form = reactive({ name: "", kind: "expense" as CategoryKind, archived: false });

function open(kind: CategoryKind, item?: LedgerCategory) {
  formError.value = "";
  editing.value = item ?? null;
  form.name = item?.name ?? "";
  form.kind = item?.kind ?? kind;
  form.archived = item?.archived ?? false;
}
function close() {
  editing.value = undefined;
  formError.value = "";
}
async function save() {
  formError.value = "";
  const payload = { name: form.name };
  try {
    const item = editing.value;
    // The kind is settable only on create: changing it would rewrite history.
    if (item) await updateCategory(item.id, { ...payload, archived: form.archived });
    else await createCategory({ ...payload, kind: form.kind });
    close();
    emit("changed");
    emit("notice", item ? "分类已更新" : "分类已添加");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
  }
}
async function remove(item: LedgerCategory) {
  if (!window.confirm(`确定删除分类“${item.name}”？已被流水使用时会提示改为归档。`)) return;
  try {
    await deleteCategory(item.id);
    close();
    emit("changed");
    emit("notice", "分类已删除");
  } catch (e) {
    emit("error", e);
  }
}
</script>

<template>
  <section class="manage-block">
    <header class="manage-heading">
      <div><h2>分类</h2><p class="summary-note">收入与支出分组独立；同类型下重名会提示已存在。</p></div>
    </header>

    <div class="category-groups">
      <div v-for="group in groups" :key="group.kind" class="category-group">
        <header class="category-group-heading">
          <h3>{{ group.label }}<span class="heading-count">{{ group.rows.length }}</span></h3>
          <button class="text-button" @click="open(group.kind)"><AppIcon name="plus" :size="14" />添加{{ group.label }}分类</button>
        </header>
        <ul v-if="group.rows.length" class="chip-list">
          <li v-for="row in group.rows" :key="row.id" class="chip-row" :class="{ inactive: row.archived }">
            <span>{{ row.name }}<span v-if="row.archived" class="tag">已归档</span></span>
            <span class="chip-actions">
              <button class="icon-button" :aria-label="`编辑 ${row.name}`" @click="open(group.kind, row)"><AppIcon name="edit" :size="14" /></button>
              <button class="icon-button danger-hover" :aria-label="`删除 ${row.name}`" @click="remove(row)"><AppIcon name="delete" :size="14" /></button>
            </span>
          </li>
        </ul>
        <p v-else class="muted small">这个分组还没有分类。</p>
      </div>
    </div>

    <ModalDialog v-if="editing !== undefined" :title="`${editing ? '编辑' : '添加'}分类`" subtitle="分类用来回答「这是什么开销」。" @close="close">
      <form class="record-form" @submit.prevent="save">
        <label>名称<input v-model="form.name" required maxlength="20" autofocus placeholder="例如：餐饮" /></label>
        <label v-if="!editing">归属<select v-model="form.kind"><option value="expense">支出</option><option value="income">收入</option></select></label>
        <p v-else class="field-hint">分类的收支归属创建后不可更改，避免历史统计被改写。</p>
        <label class="checkbox-label"><input v-model="form.archived" type="checkbox" />归档（不在记账时选择，流水保留）</label>
        <p v-if="formError" role="alert" class="form-error">{{ formError }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="close">取消</button>
          <button class="button primary" :disabled="busy">{{ busy ? "保存中…" : "保存分类" }}</button>
        </footer>
      </form>
    </ModalDialog>
  </section>
</template>

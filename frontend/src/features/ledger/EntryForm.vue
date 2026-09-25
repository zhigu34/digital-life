<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import type {
  EntryKind,
  LedgerAccount,
  LedgerCategory,
  LedgerEntry,
  LedgerPayee,
} from "../../types";
import { createPayee } from "./api";
import { entryKindLabels } from "./ledger";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";

const props = defineProps<{
  item?: LedgerEntry;
  accounts: LedgerAccount[];
  categories: LedgerCategory[];
  payees: LedgerPayee[];
  today: string;
  busy: boolean;
  error: string;
}>();
const emit = defineEmits<{
  close: [];
  save: [data: Record<string, unknown>];
  remove: [item: LedgerEntry];
  "payees-changed": [];
}>();

const kinds: EntryKind[] = ["expense", "income", "transfer"];
const form = reactive({
  kind: (props.item?.kind ?? "expense") as EntryKind,
  occurred_on: props.item?.occurred_on ?? props.today,
  amount: props.item ? (props.item.amount_cents / 100).toFixed(2) : "",
  account_id: (props.item?.account_id ?? props.accounts[0]?.id ?? null) as number | null,
  from_account_id: (props.item?.from_account_id ?? null) as number | null,
  to_account_id: (props.item?.to_account_id ?? null) as number | null,
  category_id: (props.item?.category_id ?? null) as number | null,
  note: props.item?.note ?? "",
});
const payeeName = ref(props.item?.payee_id ? (props.payees.find((p) => p.id === props.item!.payee_id)?.name ?? "") : "");
const localError = ref(""), payeeBusy = ref(false);
const isTransfer = computed(() => form.kind === "transfer");
const account = computed(() => props.accounts.find((row) => row.id === form.account_id) ?? null);
const currency = computed(() =>
  isTransfer.value
    ? (props.accounts.find((row) => row.id === form.from_account_id)?.currency ?? "CNY")
    : (account.value?.currency ?? "CNY"),
);
const categoryOptions = computed(() => props.categories.filter((row) => row.kind === form.kind));

function pickAccount(id: number) {
  form.account_id = id || null;
  // The category must match the entry kind; a stale pick would be rejected.
  if (form.category_id && !categoryOptions.value.some((row) => row.id === form.category_id))
    form.category_id = null;
}

async function resolvePayee(): Promise<number | null> {
  const name = payeeName.value.trim();
  if (!name) return null;
  const existing = props.payees.find(
    (row) => row.name.toLowerCase() === name.toLowerCase(),
  );
  if (existing) return existing.id;
  // Recording a payment should not require a trip to the dictionary first.
  payeeBusy.value = true;
  try {
    const created = await createPayee({ name });
    emit("payees-changed");
    return created.id;
  } finally {
    payeeBusy.value = false;
  }
}

async function save() {
  localError.value = "";
  const cents = Math.round(Number(form.amount) * 100);
  if (!Number.isFinite(cents) || cents < 1) {
    localError.value = "请填写大于 0 的金额";
    return;
  }
  if (isTransfer.value) {
    if (!form.from_account_id || !form.to_account_id) {
      localError.value = "请选择转出与转入账户";
      return;
    }
    if (form.from_account_id === form.to_account_id) {
      localError.value = "转出与转入账户不能相同";
      return;
    }
    if (currency.value !== props.accounts.find((row) => row.id === form.to_account_id)?.currency) {
      localError.value = "两个账户的币种不同，无法直接转账";
      return;
    }
  } else if (!form.account_id) {
    localError.value = "请选择账户";
    return;
  }

  let payeeId: number | null;
  try {
    payeeId = isTransfer.value ? null : await resolvePayee();
  } catch (e) {
    localError.value = e instanceof Error ? e.message : "商户创建失败";
    return;
  }

  const base = {
    occurred_on: form.occurred_on,
    amount_cents: cents,
    currency: currency.value,
    note: form.note,
  };
  emit("save", {
    ...base,
    kind: form.kind,
    account_id: isTransfer.value ? null : form.account_id,
    from_account_id: isTransfer.value ? form.from_account_id : null,
    to_account_id: isTransfer.value ? form.to_account_id : null,
    category_id: isTransfer.value ? null : form.category_id,
    payee_id: payeeId,
  });
}
</script>

<template>
  <ModalDialog
    :title="`${item ? '编辑' : '记一笔'}`"
    subtitle="钱花在哪里、又从哪里来，记下来就清楚了。"
    @close="emit('close')"
  >
    <form class="record-form ledger-form" @submit.prevent="save">
      <div class="tabs entry-kind-tabs" aria-label="记账类型">
        <button
          v-for="kind in kinds"
          :key="kind"
          type="button"
          :class="{ active: form.kind === kind }"
          @click="form.kind = kind"
        >
          {{ entryKindLabels[kind] }}
        </button>
      </div>

      <div class="form-grid">
        <label>金额<input v-model="form.amount" type="number" inputmode="decimal" required min="0.01" max="1000000" step="0.01" placeholder="0.00" autofocus /></label>
        <label>日期<input v-model="form.occurred_on" type="date" required :max="today" /></label>
      </div>

      <div v-if="isTransfer" class="form-grid">
        <label>转出账户<select v-model="form.from_account_id" required><option :value="null" disabled>请选择</option><option v-for="row in accounts" :key="row.id" :value="row.id">{{ row.name }}（{{ row.currency }}）</option></select></label>
        <label>转入账户<select v-model="form.to_account_id" required><option :value="null" disabled>请选择</option><option v-for="row in accounts" :key="row.id" :value="row.id">{{ row.name }}（{{ row.currency }}）</option></select></label>
      </div>
      <label v-else>账户<select :value="form.account_id ?? ''" required @change="pickAccount(Number(($event.target as HTMLSelectElement).value))"><option value="" disabled>请选择</option><option v-for="row in accounts" :key="row.id" :value="row.id">{{ row.name }}（{{ row.currency }}）</option></select></label>

      <template v-if="!isTransfer">
        <div class="form-grid">
          <label>分类 <span class="optional">选填</span><select v-model="form.category_id"><option :value="null">未分类</option><option v-for="row in categoryOptions" :key="row.id" :value="row.id">{{ row.name }}</option></select></label>
          <label>商户 <span class="optional">{{ form.kind === "expense" ? "填不存在的名称会自动新建" : "选填" }}</span><input v-model="payeeName" list="ledger-payee-options" maxlength="40" placeholder="例如：老张面馆" /><datalist id="ledger-payee-options"><option v-for="row in payees" :key="row.id" :value="row.name" /></datalist></label>
        </div>
      </template>

      <label>备注 <span class="optional">选填</span><textarea v-model="form.note" rows="2" maxlength="4000" placeholder="一些想记住的小细节…"></textarea></label>
      <p class="field-hint">转账只挪动两个账户的余额，不计入当月收支。</p>
      <p v-if="error || localError" role="alert" class="form-error">{{ localError || error }}</p>
      <footer class="modal-actions">
        <button v-if="item" type="button" class="button danger-ghost" :disabled="busy" @click="emit('remove', item)"><AppIcon name="delete" :size="15" />删除</button>
        <button type="button" class="button secondary" :disabled="busy" @click="emit('close')">取消</button>
        <button class="button primary" :disabled="busy || payeeBusy">{{ busy || payeeBusy ? "保存中…" : "保存记录" }}</button>
      </footer>
    </form>
  </ModalDialog>
</template>

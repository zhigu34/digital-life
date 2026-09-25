<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import type { AccountKind, LedgerAccount } from "../../types";
import { currencies } from "../../types";
import { money } from "../../domain";
import { createAccount, deleteAccount, updateAccount } from "./api";
import { accountKindLabels } from "./ledger";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";

const props = defineProps<{ accounts: LedgerAccount[]; busy: boolean }>();
const emit = defineEmits<{
  changed: [];
  error: [error: unknown];
  notice: [message: string];
  "view-entries": [accountId: number];
}>();

const kinds = Object.keys(accountKindLabels) as AccountKind[];
const editing = ref<LedgerAccount | null | undefined>(undefined);
const formError = ref("");
const form = reactive({
  name: "",
  kind: "debit" as AccountKind,
  currency: "CNY",
  opening: "",
  archived: false,
});
const balances = computed(() =>
  props.accounts.reduce<Record<string, number>>((totals, row) => {
    totals[row.currency] = (totals[row.currency] ?? 0) + row.balance_cents;
    return totals;
  }, {}),
);

function open(item?: LedgerAccount) {
  formError.value = "";
  editing.value = item ?? null;
  form.name = item?.name ?? "";
  form.kind = item?.kind ?? "debit";
  form.currency = item?.currency ?? "CNY";
  form.opening = item ? (item.opening_balance_cents / 100).toFixed(2) : "0.00";
  form.archived = item?.archived ?? false;
}
function close() {
  editing.value = undefined;
  formError.value = "";
}
async function save() {
  formError.value = "";
  const cents = Math.round(Number(form.opening || 0) * 100);
  if (!Number.isFinite(cents)) {
    formError.value = "期初余额请填写数字（信用卡可填负数）";
    return;
  }
  const payload = {
    name: form.name,
    kind: form.kind,
    currency: form.currency,
    opening_balance_cents: cents,
    archived: form.archived,
  };
  try {
    const item = editing.value;
    if (item) await updateAccount(item.id, payload);
    else await createAccount(payload);
    close();
    emit("changed");
    emit("notice", item ? "账户已更新" : "账户已添加");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
  }
}
async function remove(item: LedgerAccount) {
  if (!window.confirm(`确定删除账户“${item.name}”？已有流水的账户无法删除，请改用归档。`)) return;
  try {
    await deleteAccount(item.id);
    close();
    emit("changed");
    emit("notice", "账户已删除");
  } catch (e) {
    emit("error", e);
  }
}
</script>

<template>
  <section class="manage-block">
    <header class="manage-heading">
      <div><h2>账户</h2><p class="summary-note">余额 = 期初 + 收入 − 支出 ± 转账，由流水推导，不单独存一份。</p></div>
      <button class="button secondary" @click="open()"><AppIcon name="plus" :size="16" />添加账户</button>
    </header>

    <ul v-if="accounts.length" class="account-cards">
      <li v-for="item in accounts" :key="item.id" class="account-card" :class="{ inactive: item.archived }">
        <header><strong>{{ item.name }}</strong><span class="tag">{{ accountKindLabels[item.kind] }}</span><span v-if="item.archived" class="tag">已归档</span></header>
        <p class="account-balance" :class="{ negative: item.balance_cents < 0 }">{{ money(item.balance_cents, item.currency) }}</p>
        <p class="muted small">期初 {{ money(item.opening_balance_cents, item.currency) }}</p>
        <div class="account-actions">
          <button class="text-button" @click="emit('view-entries', item.id)">查看流水<AppIcon name="chevron" :size="14" /></button>
          <button class="icon-button" :aria-label="`编辑 ${item.name}`" @click="open(item)"><AppIcon name="edit" :size="16" /></button>
          <button class="icon-button danger-hover" :aria-label="`删除 ${item.name}`" @click="remove(item)"><AppIcon name="delete" :size="16" /></button>
        </div>
      </li>
    </ul>
    <p v-else class="muted small">还没有账户。先建一张常用的卡，记流水时就能挂上去。</p>
    <p v-if="Object.keys(balances).length > 1" class="summary-note">
      各币种余额分开统计，不做汇率折算：{{ Object.entries(balances).map(([currency, cents]) => `${currency} ${(cents / 100).toFixed(2)}`).join(" · ") }}
    </p>

    <ModalDialog v-if="editing !== undefined" :title="`${editing ? '编辑' : '添加'}账户`" subtitle="信用卡的期初余额可以填负数。" @close="close">
      <form class="record-form" @submit.prevent="save">
        <label>名称<input v-model="form.name" required maxlength="40" autofocus placeholder="例如：招行储蓄卡" /></label>
        <div class="form-grid">
          <label>类型<select v-model="form.kind"><option v-for="kind in kinds" :key="kind" :value="kind">{{ accountKindLabels[kind] }}</option></select></label>
          <label>币种<select v-model="form.currency"><option v-for="currency in currencies" :key="currency">{{ currency }}</option></select></label>
        </div>
        <label>期初余额（元）<input v-model="form.opening" type="number" inputmode="decimal" step="0.01" placeholder="0.00" /></label>
        <label class="checkbox-label"><input v-model="form.archived" type="checkbox" />归档（不在记账时选择，流水保留）</label>
        <p v-if="formError" role="alert" class="form-error">{{ formError }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="close">取消</button>
          <button class="button primary" :disabled="busy">{{ busy ? "保存中…" : "保存账户" }}</button>
        </footer>
      </form>
    </ModalDialog>
  </section>
</template>

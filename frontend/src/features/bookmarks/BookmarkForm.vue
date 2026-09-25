<script setup lang="ts">
import { ref } from "vue";
import type { Bookmark } from "../../types";
import { fetchBookmarkTitle } from "./api";
import AppIcon from "../../components/AppIcon.vue";
import ModalDialog from "../../components/ModalDialog.vue";

const props = defineProps<{ item?: Bookmark; folders: string[]; busy: boolean; error: string }>();
const emit = defineEmits<{
  close: [];
  save: [data: Record<string, unknown>];
  remove: [item: Bookmark];
}>();
const defaults = { url: "", title: "", note: "", folder: "", starred: false };
const form = ref<typeof defaults>({
  ...defaults,
  ...(props.item
    ? { url: props.item.url, title: props.item.title, note: props.item.note, folder: props.item.folder ?? "", starred: props.item.starred }
    : {}),
});
const localError = ref(""), titleBusy = ref(false), titleNotice = ref("");
async function lookupTitle() {
  titleNotice.value = "";
  const url = form.value.url.trim();
  if (!url) { localError.value = "先填写网址，再获取标题"; return; }
  titleBusy.value = true;
  try {
    const result = await fetchBookmarkTitle(url);
    form.value.title = result.title;
    titleNotice.value = "已填入网页标题";
  } catch (e) {
    localError.value = e instanceof Error ? e.message : "获取标题失败";
  } finally {
    titleBusy.value = false;
  }
}
function save() {
  localError.value = "";
  const url = form.value.url.trim(), title = form.value.title.trim(), folder = form.value.folder.trim();
  if (!url) { localError.value = "请填写网址"; return; }
  if (!title) { localError.value = "请填写标题"; return; }
  emit("save", { url, title, note: form.value.note.trim(), folder: folder || null, starred: form.value.starred });
}
</script>

<template>
  <ModalDialog :title="`${item ? '编辑' : '添加'}书签`" subtitle="存下想再去的地方，也记一句为什么收藏。" @close="emit('close')">
    <form class="record-form bookmark-form" @submit.prevent="save">
      <section class="form-section">
        <div class="form-section-heading"><strong>网址</strong><span>只支持 http 和 https</span></div>
        <label>网址<input v-model="form.url" required maxlength="2048" autofocus placeholder="https://example.com/docs" /></label>
        <div class="form-section-heading"><strong>标题</strong><span>可联网获取</span></div>
        <label>标题<input v-model="form.title" required maxlength="160" placeholder="例如：团队文档中心" /></label>
        <button type="button" class="text-button" :disabled="titleBusy" @click="lookupTitle">
          <AppIcon :name="titleBusy ? 'loading' : 'search'" :size="15" />{{ titleBusy ? "获取中…" : "获取标题" }}
        </button>
        <span class="field-hint">点击后由服务器访问该网页读取标题；内网地址不会抓取，请手动填写。</span>
        <p v-if="titleNotice" class="field-hint">{{ titleNotice }}</p>
      </section>
      <section class="form-section">
        <div class="form-section-heading"><strong>整理</strong><span>选填</span></div>
        <div class="form-grid">
          <label>分组<input v-model="form.folder" list="bookmark-folders" maxlength="60" placeholder="例如：运维" /><datalist id="bookmark-folders"><option v-for="name in folders" :key="name" :value="name" /></datalist></label>
          <label class="checkbox-field"><input v-model="form.starred" type="checkbox" /><span>置顶收藏</span></label>
        </div>
        <label>备注 <span class="optional">选填</span><textarea v-model="form.note" rows="3" maxlength="4000" placeholder="为什么收藏它…"></textarea></label>
      </section>
      <p v-if="error || localError" role="alert" class="form-error">{{ localError || error }}</p>
      <footer class="modal-actions">
        <button v-if="item" type="button" class="button danger-ghost" :disabled="busy" @click="emit('remove', item)"><AppIcon name="delete" :size="15" />删除</button>
        <button type="button" class="button secondary" :disabled="busy" @click="emit('close')">取消</button>
        <button class="button primary" :disabled="busy">{{ busy ? "保存中…" : "保存书签" }}</button>
      </footer>
    </form>
  </ModalDialog>
</template>

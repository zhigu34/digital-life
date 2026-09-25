<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { Bookmark } from "../../types";
import { faviconOf, filterBookmarks, foldersOf, groupBookmarks, hostOf, initialsOf } from "./bookmarks";
import { useBookmarks } from "./useBookmarks";
import AppIcon from "../../components/AppIcon.vue";
import EmptyState from "../../components/EmptyState.vue";
import BookmarkForm from "./BookmarkForm.vue";
import "./bookmarks.css";

const emit = defineEmits<{ error: [error: unknown]; notice: [message: string] }>();
const { bookmarks, loading, busy, error, load, create, update, remove, visit } = useBookmarks();
const editing = ref<Bookmark | null | undefined>(undefined), formError = ref(""), search = ref("");
const folderChoice = ref("all"), iconFailed = ref<Record<number, boolean>>({});
const ALL = "all", NONE = "__none__";
const folders = computed(() => foldersOf(bookmarks.value));
const activeFolder = computed(() =>
  folderChoice.value === ALL ? undefined : folderChoice.value === NONE ? "" : folderChoice.value,
);
const filtered = computed(() => filterBookmarks(bookmarks.value, search.value, activeFolder.value));
const groups = computed(() => groupBookmarks(filtered.value));
function folderLabel(folder: string | null): string {
  return folder ?? "未分组";
}
function open(item?: Bookmark) {
  formError.value = "";
  editing.value = item ?? null;
}
function close() {
  editing.value = undefined;
  formError.value = "";
}
async function reload() {
  try {
    await load();
  } catch (e) {
    emit("error", e);
  }
}
async function save(data: Record<string, unknown>) {
  formError.value = "";
  try {
    const wasEdit = !!editing.value;
    if (editing.value) await update(editing.value.id, data);
    else await create(data);
    close();
    emit("notice", wasEdit ? "书签已更新" : "已添加书签");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
    emit("error", e);
  }
}
async function removeItem(item: Bookmark) {
  if (!window.confirm(`确定删除“${item.title}”？删除后无法恢复。`)) return;
  try {
    await remove(item.id);
    close();
    emit("notice", "书签已删除");
  } catch (e) {
    emit("error", e);
  }
}
function openLink(item: Bookmark) {
  void visit(item.id);
}
onMounted(() => {
  void reload();
});
</script>

<template>
  <section class="page collection-page bookmarks-page">
    <div v-if="error" class="global-error" role="alert"><span>{{ error }}</span><button class="text-button" @click="reload">重新加载</button></div>
    <div v-if="loading" class="loading-line" role="status" aria-label="正在同步书签"></div>
    <header class="page-heading bookmark-heading">
      <div>
        <span class="eyebrow">SOMEWHERE TO RETURN TO</span>
        <h1>书签<span class="heading-count">{{ bookmarks.length }}</span></h1>
        <p>收藏常去的站点，写下为什么留着它。</p>
      </div>
      <button class="button primary" @click="open()"><AppIcon name="plus" :size="18" />添加书签</button>
    </header>
    <div class="collection-toolbar bookmark-toolbar">
      <label class="search-box"><AppIcon name="search" :size="17" /><input v-model="search" aria-label="搜索书签" placeholder="搜索标题、网址或备注…" /></label>
      <label class="select-field">分组<select v-model="folderChoice" aria-label="按分组筛选">
        <option :value="ALL">全部分组</option>
        <option v-for="name in folders" :key="name" :value="name">{{ name }}</option>
        <option :value="NONE">未分组</option>
      </select></label>
    </div>
    <EmptyState v-if="!loading && !bookmarks.length" icon="bookmarks" title="还没有收藏任何站点" description="把常去的网站存进来，需要时一眼就能找到。" action="添加书签" @action="open()" />
    <EmptyState v-else-if="!loading && !filtered.length" icon="search" title="没有找到对应书签" description="试试其他关键词，或切换分组筛选。" />
    <div v-else class="bookmark-groups">
      <section v-for="group in groups" :key="group.folder ?? ''" class="bookmark-group">
        <header v-if="groups.length > 1 || group.folder" class="bookmark-group-heading">
          <h2>{{ folderLabel(group.folder) }}</h2><span>{{ group.items.length }}</span>
        </header>
        <div class="bookmark-grid">
          <article v-for="item in group.items" :key="item.id" class="bookmark-card">
            <a class="bookmark-link" :href="item.url" target="_blank" rel="noopener noreferrer" @click="openLink(item)">
              <span class="bookmark-icon">
                <img v-if="faviconOf(item.url) && !iconFailed[item.id]" :src="faviconOf(item.url)" alt="" loading="lazy" @error="iconFailed[item.id] = true" />
                <span v-else class="bookmark-initials">{{ initialsOf(item.title) }}</span>
              </span>
              <span class="bookmark-main">
                <strong class="bookmark-title">{{ item.title }}<AppIcon v-if="item.starred" name="bookmarks" :size="13" class="bookmark-star" /></strong>
                <span class="bookmark-host">{{ hostOf(item.url) }}</span>
                <span v-if="item.note" class="bookmark-note">{{ item.note }}</span>
              </span>
            </a>
            <button class="bookmark-edit icon-button" :aria-label="`编辑 ${item.title}`" :disabled="busy" @click="open(item)"><AppIcon name="edit" :size="15" /></button>
          </article>
        </div>
      </section>
    </div>
    <p v-if="bookmarks.length" class="page-footnote">存下来的，都是想去的地方。</p>
    <BookmarkForm v-if="editing !== undefined" :item="editing || undefined" :folders="folders" :busy="busy" :error="formError" @close="close" @save="save" @remove="removeItem" />
  </section>
</template>

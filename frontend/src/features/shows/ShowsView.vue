<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { Show, Stats } from "../../types";
import type { ShowFilter } from "./domain";
import { filterShows, groupShowsByType } from "./domain";
import { labels } from "../../domain";
import AppIcon from "../../components/AppIcon.vue";
import EmptyState from "../../components/EmptyState.vue";
import ShowCard from "./ShowCard.vue";
import ShowForm from "./ShowForm.vue";
import { useShows } from "./useShows";

const props = defineProps<{ stats: Stats | null }>();
const emit = defineEmits<{ refresh: []; error: [error: unknown]; notice: [message: string] }>();
const { shows, loading, busy, error, load, create, update, remove, advance } = useShows();
const editing = ref<Show | null | undefined>(undefined);
const formError = ref("");
const search = ref("");
const filter = ref<ShowFilter>("all");
const tabs: ShowFilter[] = ["all", "watching", "planned", "completed", "paused"];
const filtered = computed(() => filterShows(shows.value, search.value, filter.value));
const groups = computed(() => groupShowsByType(filtered.value));
const groupLabels: Record<Show["media_type"], string> = { tv: "剧集", anime: "动漫", movie: "电影" };

async function reload() { try { await load(); } catch (e) { emit("error", e); } }
function open(item?: Show) { formError.value = ""; editing.value = item ?? null; }
function close() { editing.value = undefined; formError.value = ""; }
async function save(data: Record<string, unknown>) {
  formError.value = "";
  try {
    if (editing.value) await update(editing.value.id, data); else await create(data);
    const wasEdit = !!editing.value; close(); emit("refresh"); emit("notice", wasEdit ? "记录已更新" : "已添入你的日常");
  } catch (e) { formError.value = e instanceof Error ? e.message : "保存失败"; emit("error", e); }
}
async function removeItem(item: Show) {
  if (!window.confirm(`确定删除“${item.title}”？删除后无法恢复。`)) return;
  try { await remove(item.id); close(); emit("refresh"); emit("notice", "记录已删除"); }
  catch (e) { emit("error", e); }
}
async function advanceItem(id: number) {
  try { await advance(id); emit("refresh"); emit("notice", "又看完一集，进度已更新"); }
  catch (e) { emit("error", e); }
}
onMounted(reload);
</script>

<template>
  <section class="page collection-page shows-page">
    <div v-if="error" class="global-error" role="alert"><span>{{ error }}</span><button class="text-button" @click="reload">重新加载</button></div>
    <div v-if="loading" class="loading-line" role="status" aria-label="正在同步追剧记录"></div>
    <header class="page-heading"><div><span class="eyebrow">A GOOD STORY AWAITS</span><h1>追剧片单<span class="heading-count">{{ shows.length }}</span></h1><p>收藏想看的故事，记住每一次看到哪里。</p></div><button class="button primary" @click="open()"><AppIcon name="plus" :size="18" />添加作品</button></header>
    <section v-if="stats && shows.length" class="shows-stats" aria-label="追剧统计"><div v-for="[value,label] in [[stats.shows.watching,'在看'],[stats.shows.planned,'想看'],[stats.shows.completed,'已看完'],[stats.shows.paused,'暂搁']]" :key="label" class="summary-card"><span>{{ label }}</span><strong>{{ value }}</strong></div><div class="summary-card"><span>累计看完</span><strong>{{ stats.shows.episodes_watched }}<small>集</small></strong></div></section>
    <div class="collection-toolbar"><div class="tabs" aria-label="状态筛选"><button v-for="tab in tabs" :key="tab" :class="{active:filter===tab}" @click="filter=tab">{{ tab === 'all' ? '全部' : labels[tab] }}</button></div><label class="search-box"><AppIcon name="search" :size="17" /><input v-model="search" aria-label="搜索记录" placeholder="搜索记录…" /></label></div>
    <EmptyState v-if="!loading && !shows.length" icon="shows" title="下一段好故事，等你开启" description="添加一部想看的电影、剧集或动漫，慢慢享受。" action="添加作品" @action="open()" />
    <EmptyState v-else-if="!loading && !filtered.length" icon="search" title="没有找到对应记录" description="试试其他关键词，或切换状态筛选。" />
    <div v-else class="show-groups"><section v-for="group in groups" :key="group.type" class="show-group"><header class="show-group-heading"><h2>{{ groupLabels[group.type] }}</h2><span>{{ group.items.length }}</span></header><div class="record-list card-grid has-shows"><ShowCard v-for="item in group.items" :key="item.id" :item="item" :busy="busy" @edit="open" @advance="advanceItem" /></div></section></div>
    <p v-if="shows.length" class="page-footnote">一点一滴，都是生活的痕迹。</p>
    <ShowForm v-if="editing !== undefined" :item="editing || undefined" :busy="busy" :error="formError" @close="close" @save="save" @remove="removeItem" />
  </section>
</template>

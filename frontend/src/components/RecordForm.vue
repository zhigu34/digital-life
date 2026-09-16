<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import type { Collection, RecordItem } from "../types";
import { api, uploadPoster } from "../api";
import AppIcon from "./AppIcon.vue";
import ModalDialog from "./ModalDialog.vue";
const props = defineProps<{
  collection: Collection;
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
const titles = {
  tasks: "待办",
  expenses: "周期费用",
  shows: "追剧",
  milestones: "重要日子",
};
const defaults: Record<Collection, Record<string, any>> = {
  tasks: {
    title: "",
    notes: "",
    status: "todo",
    due_date: "",
    priority: "normal",
  },
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
  shows: {
    title: "",
    notes: "",
    media_type: "tv",
    status: "planned",
    progress: 0,
    total: "",
    score: "",
    update_weekday: "",
  },
  milestones: {
    title: "",
    notes: "",
    date: props.today,
    repeats_yearly: false,
  },
};
const form = reactive<Record<string, any>>({ ...defaults[props.collection], ...props.item });
const amount = ref(
  props.item && "amount_cents" in props.item
    ? (props.item.amount_cents / 100).toFixed(2)
    : "",
);
const localError = ref("");
const posterBusy = ref(false);
const posterError = ref("");
const posterInput = ref<HTMLInputElement>();
const canEditCover = computed(() => props.collection === "shows" && !!props.item);
const posterPreview = ref(
  !!(props.item && "poster_path" in props.item && props.item.poster_path),
);
const LOCAL_POSTER = "local:upload";
interface MetadataResult {
  source: "bangumi" | "tmdb";
  source_id: number;
  title: string;
  original_title: string | null;
  air_date: string | null;
  total_episodes: number | null;
  platform: string | null;
  image: string | null;
  seasons: number | null;
  air_status: "airing" | "ended" | "upcoming" | "released" | null;
}
const metadataResults = ref<MetadataResult[]>([]),
  metadataBusy = ref(false),
  metadataError = ref("");
const canLookup = computed(
  () => props.collection === "shows" && !props.item,
);
const lookupLabels: Record<string, string> = {
  anime: "联网搜索动漫信息",
  tv: "联网搜索剧集信息",
  movie: "联网搜索电影信息",
};
const airStatus: Record<string, string> = {
  airing: "连载中",
  ended: "已完结",
  upcoming: "未开播",
  released: "已上映",
};
// Both providers stay a free choice; the type only picks the initial default.
const metadataSource = ref<"bangumi" | "tmdb">(
  form.media_type === "anime" ? "bangumi" : "tmdb",
);
watch(
  () => form.media_type,
  (type) => {
    metadataSource.value = type === "anime" ? "bangumi" : "tmdb";
    metadataResults.value = [];
    metadataError.value = "";
  },
);
async function lookupMetadata() {
  metadataError.value = "";
  metadataResults.value = [];
  const keyword = String(form.title).trim();
  if (!keyword) {
    metadataError.value = "先填写名称关键词，再联网搜索";
    return;
  }
  metadataBusy.value = true;
  try {
    const data = await api<{ results: MetadataResult[] }>(
      `/shows/metadata?keyword=${encodeURIComponent(keyword)}&media_type=${form.media_type}&source=${metadataSource.value}`,
    );
    metadataResults.value = data.results;
    if (!data.results.length)
      metadataError.value = "没有找到相关作品，可以直接手动填写";
  } catch (e) {
    metadataError.value = e instanceof Error ? e.message : "搜索失败";
  } finally {
    metadataBusy.value = false;
  }
}
function applyMetadata(result: MetadataResult) {
  form.title = result.title;
  if (result.total_episodes) form.total = result.total_episodes;
  form.source = result.source;
  form.source_id = result.source_id;
  form.poster_path = result.image ?? "";
  form.seasons = result.seasons ?? "";
  form.air_status = result.air_status ?? "";
  metadataResults.value = [];
}
function posterSrc(item: RecordItem | undefined) {
  return item && "poster_path" in item && item.poster_path
    ? `/api/shows/${item.id}/poster`
    : "";
}
async function pickPoster() {
  posterInput.value?.click();
}
async function uploadPosterFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !props.item) return;
  posterError.value = "";
  posterBusy.value = true;
  try {
    await uploadPoster(`/shows/${props.item.id}/poster`, file);
    posterPreview.value = true;
    form.poster_path = LOCAL_POSTER;
  } catch (e) {
    posterError.value = e instanceof Error ? e.message : "上传失败";
  } finally {
    posterBusy.value = false;
  }
}
function clearPoster() {
  form.poster_path = "";
  posterPreview.value = false;
  posterError.value = "";
}
function save() {
  localError.value = "";
  const data = { ...form };
  delete data.id;
  delete data.created_at;
  if (props.collection === "tasks") data.due_date = data.due_date || null;
  if (props.collection === "expenses") {
    data.amount_cents = Math.round(Number(amount.value) * 100);
    data.period_months = Number(data.period_months);
    data.anchor_day = Number(data.anchor_day);
  }
  if (props.collection === "shows") {
    for (const key of ["total", "score", "update_weekday", "seasons", "source_id"])
      data[key] =
        data[key] === "" || data[key] === null ? null : Number(data[key]);
    for (const key of ["source", "air_status", "poster_path"])
      data[key] = data[key] === "" || data[key] === null ? null : data[key];
    data.progress = Number(data.progress);
    if (data.total !== null && data.progress > data.total) {
      localError.value = "已看进度不能大于总集数";
      return;
    }
  }
  emit("save", data);
}
</script>
<template>
  <ModalDialog
    :title="`${item ? '编辑' : '添加'}${titles[collection]}`"
    subtitle="给生活中的这件事，留一个位置。"
    @close="emit('close')"
    ><form class="record-form" @submit.prevent="save">
      <label
        >名称<input
          v-model="form.title"
          required
          :maxlength="
            collection === 'tasks' || collection === 'shows' ? 160 : 120
          "
          autofocus
          :placeholder="
            {
              tasks: '例如：读完书架上的那本书',
              expenses: '例如：云存储订阅',
              shows: '例如：最近想看的那部剧',
              milestones: '例如：第一次出发的日子',
            }[collection]
          " /></label
      ><template v-if="collection === 'tasks'"
        ><div class="form-grid">
          <label
            >状态<select v-model="form.status">
              <option value="todo">待办</option>
              <option value="doing">进行中</option>
              <option value="waiting">等待中</option>
              <option value="done">已完成</option>
            </select></label
          ><label
            >优先级<select v-model="form.priority">
              <option value="low">低优先</option>
              <option value="normal">普通</option>
              <option value="high">高优先</option>
            </select></label
          >
        </div>
        <label
          >截止日期 <span class="optional">选填</span
          ><input v-model="form.due_date" type="date" /></label></template
      ><template v-if="collection === 'expenses'"
        ><div class="form-grid">
          <label
            >每期金额<input
              v-model="amount"
              type="number"
              required
              min="0.01"
              max="1000000"
              step="0.01"
              placeholder="0.00" /></label
          ><label
            >币种<select v-model="form.currency">
              <option
                v-for="currency in ['CNY', 'USD', 'EUR', 'JPY', 'HKD']"
                :key="currency"
              >
                {{ currency }}
              </option>
            </select></label
          ><label
            >付费周期<select v-model="form.period_months">
              <option :value="1">每月</option>
              <option :value="3">每季度</option>
              <option :value="12">每年</option>
            </select></label
          ><label
            >下次应付<input
              v-model="form.next_due"
              type="date"
              required
              @change="form.anchor_day = Number(form.next_due.slice(-2))"
          /></label>
        </div>
        <label
          >固定扣费日 <span class="optional">短月自动取月底</span
          ><input
            v-model="form.anchor_day"
            type="number"
            min="1"
            max="31"
            required /></label
        ><label class="checkbox-label"
          ><input
            v-model="form.active"
            type="checkbox"
          />正在使用（计入费用统计）</label
        ></template
      ><template v-if="collection === 'shows'"
        ><div class="form-grid">
          <label
            >类型<select v-model="form.media_type">
              <option value="tv">剧集</option>
              <option value="anime">动漫</option>
              <option value="movie">电影</option>
            </select></label
          ><label
            >状态<select v-model="form.status">
              <option value="planned">想看</option>
              <option value="watching">在看</option>
              <option value="completed">已看完</option>
              <option value="paused">暂搁</option>
            </select></label
          ><label
            >已看集数<input
              v-model="form.progress"
              type="number"
              max="1000000"
              min="0"
              step="1"
              required /></label
          ><label
            >总集数 <span class="optional">选填</span
            ><input
              v-model="form.total"
              type="number"
              max="1000000"
              min="1"
              step="1"
              placeholder="尚未确定" /></label
          ><label
            >我的评分 <span class="optional">1–10</span
            ><input
              v-model="form.score"
              type="number"
              min="1"
              max="10"
              step="1"
              placeholder="尚未评分" /></label
          ><label
            >更新日<select v-model="form.update_weekday">
              <option value="">不固定</option>
              <option
                v-for="(day, index) in [
                  '周一',
                  '周二',
                  '周三',
                  '周四',
                  '周五',
                  '周六',
                  '周日',
                ]"
                :key="index"
                :value="index"
              >
                {{ day }}
              </option>
            </select></label
          >
        </div>
        <div v-if="canLookup" class="metadata-lookup">
          <div class="metadata-toolbar">
            <div class="tabs metadata-source" aria-label="信息源">
              <button
                type="button"
                :class="{ active: metadataSource === 'bangumi' }"
                @click="metadataSource = 'bangumi'"
              >
                Bangumi
              </button>
              <button
                type="button"
                :class="{ active: metadataSource === 'tmdb' }"
                @click="metadataSource = 'tmdb'"
              >
                TMDB
              </button>
            </div>
            <button
              type="button"
              class="text-button"
              :disabled="metadataBusy"
              @click="lookupMetadata"
            >
              <AppIcon :name="metadataBusy ? 'loading' : 'search'" :size="15" />{{
                metadataBusy ? "搜索中…" : lookupLabels[form.media_type]
              }}
            </button>
          </div>
          <span class="field-hint"
            >手动触发；TMDB 需在 .env 配置 DIGITAL_LIFE_TMDB_API_KEY</span
          >
          <p v-if="metadataError" class="field-hint" role="alert">
            {{ metadataError }}
          </p>
          <ul v-if="metadataResults.length" class="metadata-results">
            <li v-for="result in metadataResults" :key="result.source_id">
              <button type="button" @click="applyMetadata(result)">
                <img
                  v-if="result.image"
                  :src="result.image"
                  alt=""
                  loading="lazy"
                  @error="(event) => ((event.target as HTMLImageElement).style.display = 'none')"
                />
                <div class="metadata-main">
                  <strong>{{ result.title }}</strong>
                  <span class="metadata-tags">
                    <em v-if="result.platform">{{ result.platform }}</em>
                    <em v-if="result.seasons">{{ result.seasons }} 季</em>
                    <em v-if="result.air_status">{{ airStatus[result.air_status] }}</em>
                  </span>
                  <span>{{
                    (result.total_episodes
                      ? `${result.total_episodes} 集`
                      : "集数未知") +
                    (result.air_date ? ` · ${result.air_date}` : "")
                  }}</span>
                </div>
              </button>
            </li>
          </ul>
        </div>
        <div v-if="canEditCover" class="poster-editor">
          <span class="field-label">封面</span>
          <div class="poster-editor-body">
            <div class="poster-thumb">
              <img
                v-if="posterPreview"
                :src="posterSrc(props.item)"
                :alt="form.title"
                @error="(event) => ((event.target as HTMLImageElement).style.display = 'none')"
              /><AppIcon v-else name="shows" :size="26" />
            </div>
            <div class="poster-editor-actions">
              <input
                ref="posterInput"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                hidden
                @change="uploadPosterFile"
              />
              <button
                type="button"
                class="text-button"
                :disabled="posterBusy"
                @click="pickPoster"
              >
                <AppIcon :name="posterBusy ? 'loading' : 'plus'" :size="14" />{{
                  posterBusy ? "上传中…" : "上传本地图片"
                }}
              </button>
              <button
                v-if="posterPreview"
                type="button"
                class="text-button"
                @click="clearPoster"
              >
                <AppIcon name="close" :size="14" />清除封面
              </button>
            </div>
          </div>
          <p v-if="posterError" class="field-hint" role="alert">
            {{ posterError }}
          </p>
          <p class="field-hint">
            上传或重新刮削会覆盖当前封面；链接封面需为 image.tmdb.org 或
            lain.bgm.tv 图片地址。
          </p>
        </div></template
      ><template v-if="collection === 'milestones'"
        ><label>日期<input v-model="form.date" type="date" required /></label
        ><label class="checkbox-label"
          ><input
            v-model="form.repeats_yearly"
            type="checkbox"
          />每年纪念这个日子</label
        >
        <p class="field-hint">
          2 月 29 日的周年，在平年按 2 月 28 日计算。
        </p></template
      ><label
        >备注 <span class="optional">选填</span
        ><textarea
          v-model="form.notes"
          rows="3"
          maxlength="4000"
          placeholder="一些想记住的小细节…"
        ></textarea>
      </label>
      <p v-if="error || localError" role="alert" class="form-error">
        {{ localError || error }}
      </p>
      <footer class="modal-actions">
        <button
          v-if="item"
          type="button"
          class="button danger-ghost"
          :disabled="busy"
          @click="emit('remove', item)"
        >
          <AppIcon name="delete" :size="15" />删除
        </button>
        <button
          type="button"
          class="button secondary"
          :disabled="busy"
          @click="emit('close')"
        >
          取消</button
        ><button class="button primary" :disabled="busy">
          {{ busy ? "保存中…" : "保存记录" }}
        </button>
      </footer>
    </form></ModalDialog
  >
</template>

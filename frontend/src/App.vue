<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { api, ApiError, setCsrf } from "./api";
import { calendarDate } from "./domain";
import type { User, Records, Collection, Page, RecordItem, Maintenance, Project, Stats } from "./types";
import AppIcon from "./components/AppIcon.vue";
import RecordForm from "./components/RecordForm.vue";
import LoginView from "./views/LoginView.vue";
import TodayView from "./views/TodayView.vue";
import CalendarView from "./views/CalendarView.vue";
import ShowsView from "./features/shows/ShowsView.vue";
import LedgerView from "./features/ledger/LedgerView.vue";
import ProfileView from "./views/ProfileView.vue";
import AdminView from "./views/AdminView.vue";
import MaintenanceView from "./views/MaintenanceView.vue";
import NotesView from "./views/NotesView.vue";
import MilestonesView from "./views/MilestonesView.vue";
import ProjectsView from "./views/ProjectsView.vue";
import TasksView from "./features/tasks/TasksView.vue";
import BookmarksView from "./features/bookmarks/BookmarksView.vue";
import type { LedgerTab } from "./features/ledger/ledger";
type GenericCollection = Exclude<Collection, "shows" | "expenses">;
const user=ref<User|null>(null),initializing=ref(true),loading=ref(false),busy=ref(false),error=ref(""),loginError=ref(""),notice=ref("");
const records=reactive<Records>({tasks:[],expenses:[],shows:[],milestones:[],maintenance:[],notes:[],groups:[],projects:[]});
const stats=ref<Stats|null>(null),showCreateRequest=ref(0),expenseCreateRequest=ref(0),ledgerStartTab=ref<LedgerTab|null>(null),taskCreateRequest=ref<{kind:"todo"|"group";nonce:number}|null>(null),checkRequest=ref<{groupId:number;itemId:number;nonce:number}|null>(null);
const page=ref<Page>("today"),moreOpen=ref(false),editing=ref<{collection:GenericCollection;item?:RecordItem}|null>(null),formError=ref("");
const now=ref(new Date()),today=computed(()=>calendarDate(user.value?.timezone??"Asia/Shanghai",now.value));
const navigation:[Page,string,string][]=[["today","今日概览","你的生活，此刻"],["calendar","日历",""],["tasks","任务",""],["projects","在做",""],["expenses","记账",""],["shows","追剧片单",""],["milestones","重要日子",""],["maintenance","周期维护",""],["notes","文字随记",""],["bookmarks","书签",""]];
const pageLabels:Record<Page,string>={today:"今日概览",calendar:"日历",tasks:"任务",projects:"在做",expenses:"记账",shows:"追剧片单",milestones:"重要日子",maintenance:"周期维护",notes:"文字随记",bookmarks:"书签",profile:"个人设置",admin:"账户管理"};
const mobilePrimary:Page[]=["today","calendar","tasks","expenses"],secondaryPages:Page[]=["projects","shows","milestones","maintenance","notes","bookmarks"];
const mobileNavLabels:Record<string,string>={today:"今日",calendar:"日历",tasks:"任务",projects:"在做",expenses:"记账",shows:"追剧",milestones:"日子",maintenance:"维护",notes:"随记",bookmarks:"书签"};
let noticeTimer:ReturnType<typeof setTimeout>,clockTimer:ReturnType<typeof setInterval>,accountVersion=0;
function clear(){accountVersion++;user.value=null;setCsrf("");Object.assign(records,{tasks:[],expenses:[],shows:[],milestones:[],maintenance:[],notes:[],groups:[],projects:[]});stats.value=null;editing.value=null;showCreateRequest.value=0;expenseCreateRequest.value=0;ledgerStartTab.value=null;taskCreateRequest.value=null;checkRequest.value=null;page.value="today";error.value="";notice.value="";theme();}
function notify(message:string){notice.value=message;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>notice.value="",4200);}
function handleError(e:unknown){if(e instanceof ApiError&&e.status===401){clear();loginError.value="登录已过期，请重新登录";return;}error.value=e instanceof Error?e.message:"连接失败，请检查网络后重试";}
async function load(){const version=accountVersion;loading.value=true;error.value="";try{const [tasks,expenses,shows,milestones,maintenance,notes,groups,projects,statsData]=await Promise.all([api<Records["tasks"]>("/tasks"),api<Records["expenses"]>("/expenses"),api<Records["shows"]>("/shows"),api<Records["milestones"]>("/milestones"),api<Records["maintenance"]>("/maintenance"),api<Records["notes"]>("/notes"),api<Records["groups"]>("/groups"),api<Records["projects"]>("/projects"),api<Stats>(`/stats?end_month=${today.value.slice(0,7)}`)]);if(version===accountVersion){Object.assign(records,{tasks,expenses,shows,milestones,maintenance,notes,groups,projects});stats.value=statsData;}}catch(e){if(version===accountVersion)handleError(e);}finally{if(version===accountVersion)loading.value=false;}}
async function login(username:string,password:string){busy.value=true;loginError.value="";try{clear();const session=await api<{user:User;csrf_token:string}>("/auth/login","POST",{username,password});user.value=session.user;setCsrf(session.csrf_token);await load();}catch(e){loginError.value=e instanceof Error?e.message:"登录失败，请重试";}finally{busy.value=false;}}
async function logout(){busy.value=true;try{await api("/auth/logout","POST");clear();}catch(e){handleError(e);}finally{busy.value=false;}}
function navigate(next:Page,ledgerTab?:LedgerTab){moreOpen.value=false;page.value=next;editing.value=null;showCreateRequest.value=0;expenseCreateRequest.value=0;taskCreateRequest.value=null;checkRequest.value=null;ledgerStartTab.value=next==="expenses"?ledgerTab??null:null;window.scrollTo({top:0,behavior:"smooth"});}
function open(collection:GenericCollection,item?:RecordItem){formError.value="";editing.value={collection,item};}
function createFromToday(collection:Collection){if(collection==="shows"){navigate("shows");showCreateRequest.value++;return;}if(collection==="expenses"){navigate("expenses");expenseCreateRequest.value++;return;}if(collection==="tasks"){requestTaskCreate("todo");return;}open(collection);}
/** One-off to-dos and long-term tasks are separate shapes: two entry points. */
function requestTaskCreate(kind:"todo"|"group"){navigate("tasks");taskCreateRequest.value={kind,nonce:Date.now()};}
function requestCheck(groupId:number,itemId:number){navigate("tasks");checkRequest.value={groupId,itemId,nonce:Date.now()};}
function syncGroups(groups:Records["groups"]){records.groups=groups;}
async function refreshStats(){try{stats.value=await api<Stats>(`/stats?end_month=${today.value.slice(0,7)}`);}catch(e){handleError(e);}}
function syncShows(shows:Records["shows"]){records.shows=shows;void refreshStats();}
function syncLedger(bills:Records["expenses"]){records.expenses=bills;void refreshStats();}
async function save(data:Record<string,unknown>){if(!editing.value)return;busy.value=true;formError.value="";const {collection,item}=editing.value;try{await api(`/${collection}${item?`/${item.id}`:""}`,item?"PATCH":"POST",data);editing.value=null;await load();notify(item?"记录已更新":"已添入你的日常");}catch(e){if(e instanceof ApiError&&e.status===401)handleError(e);else formError.value=e instanceof Error?e.message:"保存失败";}finally{busy.value=false;}}
async function remove(collection:GenericCollection,item:RecordItem){if(!window.confirm(`确定删除“${item.title}”？删除后无法恢复。`))return;editing.value=null;await mutate(`/${collection}/${item.id}`,"DELETE",undefined,"记录已删除");}
async function mutate(path:string,method:string,data?:unknown,message="已更新"){busy.value=true;error.value="";try{await api(path,method,data);await load();notify(message);}catch(e){handleError(e);}finally{busy.value=false;}}
async function removeMaintenance(item:Maintenance){if(!window.confirm(`确定删除“${item.title}”及其全部完成历史？删除后无法恢复。`))return;await mutate(`/maintenance/${item.id}`,"DELETE",undefined,"维护事项及历史已删除");}
async function saveProject(data:Record<string,unknown>,id?:number){busy.value=true;formError.value="";try{await api(`/projects${id?`/${id}`:""}`,id?"PATCH":"POST",data);await load();notify(id?"在做已更新":"已加入在做");}catch(e){handleError(e);}finally{busy.value=false;}}
async function removeProject(item:Project){if(!window.confirm(`确定删除“${item.title}”？删除后无法恢复。`))return;busy.value=true;try{await api(`/projects/${item.id}`,"DELETE");await load();notify("在做已删除");}catch(e){handleError(e);}finally{busy.value=false;}}
function action(collection:GenericCollection,id:number,kind:string,data?:unknown){if(kind==="pay"&&!window.confirm("确认本期已经支付？下次应付日期将向后推进一个周期。"))return;return mutate(`/${collection}/${id}${kind==="status"?"":`/${kind}`}`,kind==="status"?"PATCH":"POST",data,kind==="pay"?"本期已付，下次日期已更新":"状态已更新");}
async function profile(data:unknown){busy.value=true;try{user.value=await api<User>("/auth/profile","PATCH",data);notify("个人资料已保存");}catch(e){handleError(e);}finally{busy.value=false;}}
async function password(data:unknown){busy.value=true;try{await api("/auth/password","POST",data);clear();loginError.value="密码已更新，请使用新密码登录";}catch(e){handleError(e);}finally{busy.value=false;}}
async function exportData(){busy.value=true;try{const data=await api("/export");const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download=`digital-life-${today.value}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify("你的数据已导出");}catch(e){handleError(e);}finally{busy.value=false;}}
async function importData(data:unknown){busy.value=true;error.value="";try{const result=await api<{imported:Record<string,number>}>("/import","POST",data);await load();notify(`已导入 ${Object.values(result.imported).reduce((a,b)=>a+b,0)} 条记录`);}catch(e){handleError(e);}finally{busy.value=false;}}
const media=window.matchMedia("(prefers-color-scheme: dark)"),THEME_KEY="digital-life-theme";
function storedTheme(){try{return localStorage.getItem(THEME_KEY)||"light";}catch{return "light";}}
// 服务端 user.theme 是权威值；未登录时用本地缓存的偏好，登出后也保持它，避免闪回浅色。
function theme(){const choice=user.value?.theme??storedTheme();try{localStorage.setItem(THEME_KEY,choice);}catch{/* 隐私模式下写不进去，忽略 */}document.documentElement.dataset.theme=choice==="dark"||(choice==="system"&&media.matches)?"dark":"light";}
watch(()=>user.value?.theme,theme);
onMounted(async()=>{media.addEventListener("change",theme);clockTimer=setInterval(()=>now.value=new Date(),60000);try{const session=await api<{user:User;csrf_token:string}>("/auth/session");user.value=session.user;setCsrf(session.csrf_token);await load();}catch(e){if(!(e instanceof ApiError&&e.status===401))loginError.value=e instanceof Error?e.message:"无法连接服务器";}finally{initializing.value=false;}});
onUnmounted(()=>{media.removeEventListener("change",theme);clearInterval(clockTimer);clearTimeout(noticeTimer);});
</script>
<template>
  <div v-if="initializing" class="initial-loading"><span class="brand-mark"><AppIcon name="leaf" :size="30" /></span><p>正在打开你的生活空间…</p><AppIcon name="loading" class="spin" /></div>
  <LoginView v-else-if="!user" :busy="busy" :error="loginError" @login="login" />
  <div v-else class="app-shell">
    <aside class="sidebar"><button class="brand" @click="navigate('today')"><span class="brand-mark"><AppIcon name="leaf" :size="23" /></span>digital life<span class="brand-dot">.</span></button><span class="sidebar-label">我的生活空间</span><nav class="main-nav" aria-label="主导航"><button v-for="[id,label] in navigation" :key="id" :aria-label="id === 'today' ? '今日总览' : label" :class="{active:page===id}" @click="navigate(id)"><AppIcon :name="id" /><span>{{label}}</span><span v-if="id==='tasks'&&records.tasks.some(t=>t.status!=='done')" class="nav-count">{{records.tasks.filter(t=>t.status!=="done").length}}</span><span v-if="page===id" class="nav-active-dot"></span></button></nav><div class="sidebar-bottom"><div class="sidebar-note"><AppIcon name="sun" :size="24" /><p>小事有条理，<br />生活有余地。</p><span>MAKE ROOM FOR LIFE</span></div><button v-if="user.is_admin" aria-label="账号管理" :class="['sidebar-option',{active:page==='admin'}]" @click="navigate('admin')"><AppIcon name="admin" :size="18" />账户管理</button><button :class="['sidebar-option',{active:page==='profile'}]" @click="navigate('profile')"><AppIcon name="profile" :size="18" />个人设置</button><div class="sidebar-user"><span class="avatar">{{user.display_name.slice(0,1)}}</span><button @click="navigate('profile')"><strong>{{user.display_name}}</strong><small>我的私人空间</small></button><button class="icon-button" aria-label="退出登录" :disabled="busy" @click="logout"><AppIcon name="logout" :size="17" /></button></div></div></aside>
    <main class="main-shell"><header class="topbar"><div class="breadcrumb"><span>我的空间</span><AppIcon name="chevron" :size="13" /><strong>{{pageLabels[page]}}</strong></div><div class="topbar-right"><span class="privacy-dot"></span><span>只属于你的日常</span><button v-if="user.is_admin" class="mobile-admin icon-button" aria-label="账号管理" @click="navigate('admin')"><AppIcon name="admin" :size="18" /></button><button class="mobile-avatar avatar" aria-label="个人设置" @click="navigate('profile')">{{user.display_name.slice(0,1)}}</button></div></header>
      <div v-if="error" class="global-error" role="alert"><span>{{error}}</span><button class="text-button" @click="load">重新加载</button><button class="icon-button" aria-label="关闭错误提示" @click="error='' "><AppIcon name="close" :size="16" /></button></div><div v-if="loading" class="loading-line" role="status" aria-label="正在同步记录"></div>
      <TodayView v-if="page==='today'" :user="user" :records="records" :today="today" :busy="busy" @navigate="navigate" @create="createFromToday" @complete="(id)=>action('tasks',id,'status',{status:'done'})" @checkin="requestCheck" />
      <CalendarView v-else-if="page==='calendar'" :records="records" :today="today" @navigate="navigate" />
      <ShowsView v-else-if="page==='shows'" :key="user.id" :stats="stats" :create-request="showCreateRequest" @sync="syncShows" @error="handleError" @notice="notify" />
      <TasksView v-else-if="page==='tasks'" :key="user.id" :user-id="user.id" :tasks="records.tasks" :today="today" :busy="busy" :create-request="taskCreateRequest" :check-request="checkRequest" @sync="syncGroups" @error="handleError" @notice="notify" @create="open('tasks')" @toggle-task="(task)=>action('tasks',task.id,'status',{status:task.status==='done'?'todo':'done'})" @edit-task="(task)=>open('tasks',task)" @remove-task="(task)=>remove('tasks',task)" />
      <MilestonesView v-else-if="page==='milestones'" :key="page" :records="records" :today="today" @create="open('milestones')" @edit="(item)=>open('milestones',item)" @remove="(item)=>remove('milestones',item)" />
      <LedgerView v-else-if="page==='expenses'" :key="user.id" :stats="stats" :today="today" :bills="records.expenses" :create-request="expenseCreateRequest" :start-tab="ledgerStartTab" @sync="syncLedger" @error="handleError" @notice="notify" />
      <MaintenanceView v-else-if="page==='maintenance'" :key="user.id" :items="records.maintenance" :stats="stats" :today="today" :parent-busy="busy" @refresh="load" @error="handleError" @notice="notify" @remove="removeMaintenance" />
      <ProjectsView v-else-if="page==='projects'" :key="user.id" :projects="records.projects" :busy="busy" @save="saveProject" @remove="removeProject" @error="handleError" />
      <NotesView v-else-if="page==='notes'" :key="user.id" :items="records.notes" :today="today" :parent-busy="busy" @refresh="load" @error="handleError" @notice="notify" />
      <BookmarksView v-else-if="page==='bookmarks'" :key="user.id" @error="handleError" @notice="notify" />
      <ProfileView v-else-if="page==='profile'" :user="user" :busy="busy" @profile="profile" @password="password" @export="exportData" @import="importData" @logout="logout" />
      <AdminView v-else-if="page==='admin'&&user.is_admin" :user="user" @error="handleError" @notice="notify" />
    </main>
    <nav class="mobile-nav" aria-label="移动端导航"><button v-for="id in mobilePrimary" :key="id" :aria-label="id === 'today' ? '今日总览' : pageLabels[id]" :class="{active:page===id}" @click="navigate(id)"><AppIcon :name="id" :size="21" /><span>{{mobileNavLabels[id]}}</span></button><button :class="{active:moreOpen||secondaryPages.includes(page)}" :aria-expanded="moreOpen" aria-label="更多页面" @click="moreOpen=!moreOpen"><AppIcon name="menu" :size="21" /><span>更多</span></button></nav>
    <div v-if="moreOpen" class="mobile-more-backdrop" aria-label="关闭更多菜单" @click="moreOpen=false"></div>
    <nav v-if="moreOpen" class="mobile-more-sheet" aria-label="更多页面"><button v-for="id in secondaryPages" :key="id" :class="{active:page===id}" @click="navigate(id)"><AppIcon :name="id" :size="19" /><span>{{pageLabels[id]}}</span></button><button v-if="user.is_admin" :class="{active:page==='admin'}" @click="navigate('admin')"><AppIcon name="admin" :size="19" /><span>账户管理</span></button><button :class="{active:page==='profile'}" @click="navigate('profile')"><AppIcon name="profile" :size="19" /><span>个人设置</span></button></nav>
    <RecordForm v-if="editing" :key="`${editing.collection}-${editing.item?.id ?? 'new'}`" :collection="editing.collection" :item="editing.item" :today="today" :busy="busy" :error="formError" @close="editing=null" @save="save" @remove="(item)=>remove(editing!.collection,item)" />
    <Transition name="toast"><div v-if="notice" class="toast" role="status"><AppIcon name="check" :size="18" />{{notice}}</div></Transition>
  </div>
</template>
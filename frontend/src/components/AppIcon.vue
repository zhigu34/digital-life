<script setup lang="ts">
import {
  LayoutDashboard,
  Wrench,
  History,
  CheckCheck,
  Wallet,
  Clapperboard,
  CalendarHeart,
  Settings2,
  ShieldCheck,
  Plus,
  ArrowUpRight,
  ArrowRight,
  ChevronRight,
  LogOut,
  X,
  Pencil,
  Trash2,
  Check,
  Circle,
  Search,
  Leaf,
  Sun,
  Download,
  Play,
  LoaderCircle,
  Menu,
  CalendarDays,
  NotebookPen,
  Sparkles,
  MoreHorizontal,
} from "lucide-vue-next";
const icons = {
  today: LayoutDashboard,
  maintenance: Wrench,
  history: History,
  tasks: CheckCheck,
  expenses: Wallet,
  shows: Clapperboard,
  milestones: CalendarHeart,
  profile: Settings2,
  admin: ShieldCheck,
  plus: Plus,
  up: ArrowUpRight,
  arrow: ArrowRight,
  chevron: ChevronRight,
  logout: LogOut,
  close: X,
  edit: Pencil,
  delete: Trash2,
  check: Check,
  circle: Circle,
  search: Search,
  leaf: Leaf,
  sun: Sun,
  download: Download,
  play: Play,
  loading: LoaderCircle,
  menu: Menu,
  calendar: CalendarDays,
  notes: NotebookPen,
  sparkles: Sparkles,
  more: MoreHorizontal,
};
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 });
</script>
<template>
  <component
    :is="icons[name as keyof typeof icons] || icons.leaf"
    :size="size"
    :stroke-width="1.7"
    aria-hidden="true"
  />
</template>

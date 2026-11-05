<script setup lang="ts">
// BigScreenPreview.vue — 大屏总览布局实验场；/overview 保持原样，满意后再切换主页。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/api/client';
import type { Overview } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import LayoutA from './LayoutA.vue';
import LayoutB from './LayoutB.vue';
import LayoutC from './LayoutC.vue';
import LayoutD from './LayoutD.vue';
import type { BigScreenData } from './shared';
import { sortRunners } from './shared';

const route = useRoute();
const router = useRouter();
const realtime = useRealtimeStore();
const settings = useSettingsStore();
const data = ref<BigScreenData | null>(null);
const error = ref('');
const loading = ref(true);
const now = ref(new Date());
const layout = ref<'a' | 'b' | 'c' | 'd'>('a');
const layouts = [
  { key: 'a', label: 'A', name: '指挥中心' },
  { key: 'b', label: 'B', name: '交易台' },
  { key: 'c', label: 'C', name: '矩阵' },
  { key: 'd', label: 'D', name: '纸面报告' },
] as const;
let clockTimer: number | undefined;
let pollTimer: number | undefined;

const activeLayout = computed(() => layouts.find((item) => item.key === layout.value) || layouts[0]);
const timeText = computed(() => now.value.toLocaleTimeString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' }));
const dateText = computed(() => now.value.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', weekday: 'short', timeZone: 'Asia/Shanghai' }));

function setLayout(next: string): void {
  if (!['a', 'b', 'c', 'd'].includes(next)) return;
  layout.value = next as typeof layout.value;
  void router.replace({ query: { ...route.query, layout: next } });
}

async function load(initial = false): Promise<void> {
  if (initial) loading.value = true;
  try {
    const overview = await api.overview();
    data.value = {
      overview,
      runners: sortRunners(overview.runners || []),
      accounts: overview.accounts || [],
    };
    error.value = '';
  } catch (err) {
    error.value = err instanceof Error ? err.message : '大屏数据加载失败';
  } finally {
    loading.value = false;
  }
}

watch(() => route.query.layout, (value) => {
  const next = typeof value === 'string' ? value : 'a';
  if (['a', 'b', 'c', 'd'].includes(next)) layout.value = next as typeof layout.value;
}, { immediate: true });
watch(() => settings.refreshSeq, () => { void load(false); });
watch(() => realtime.lastProcessChangeAt, () => { void load(false); });

onMounted(() => {
  void load(true);
  clockTimer = window.setInterval(() => { now.value = new Date(); }, 1000);
  pollTimer = window.setInterval(() => { if (!document.hidden) void load(false); }, 15000);
});
onBeforeUnmount(() => {
  window.clearInterval(clockTimer);
  window.clearInterval(pollTimer);
});
</script>

<template>
  <div class="bigscreen-root">
    <div v-if="loading && !data" class="bs-loading">
      <div class="pulse" />
      <span>正在加载大屏数据</span>
    </div>
    <div v-else-if="error && !data" class="bs-loading">
      <span>{{ error }}</span>
      <router-link to="/overview" class="bs-link">返回工作台</router-link>
    </div>
    <template v-else-if="data">
      <LayoutA v-if="layout === 'a'" :data="data" :now="now" :time-text="timeText" :date-text="dateText" />
      <LayoutB v-else-if="layout === 'b'" :data="data" :now="now" :time-text="timeText" :date-text="dateText" />
      <LayoutC v-else-if="layout === 'c'" :data="data" :now="now" :time-text="timeText" :date-text="dateText" />
      <LayoutD v-else :data="data" :now="now" :time-text="timeText" :date-text="dateText" />
    </template>

    <div class="layout-dock">
      <span class="dock-label">布局预览</span>
      <button v-for="item in layouts" :key="item.key" type="button" :class="{ active: layout === item.key }" :title="item.name" @click="setLayout(item.key)">{{ item.label }}</button>
      <span class="dock-current">{{ activeLayout.name }}</span>
      <router-link to="/overview" class="dock-back">返回工作台</router-link>
    </div>
  </div>
</template>

<style scoped>
.bigscreen-root { width: 100vw; height: 100vh; overflow: hidden; background: var(--bg); color: var(--text); }
.bs-loading { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; gap: 12px; color: var(--text-2); font-size: 14px; }
.pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--primary); animation: pulse 1.2s ease-in-out infinite; }
.bs-link { color: var(--primary); }
.layout-dock { position: fixed; right: 18px; bottom: 16px; z-index: 30; display: flex; align-items: center; gap: 5px; padding: 5px 6px 5px 10px; border: 1px solid rgba(125, 139, 161, 0.22); border-radius: 9px; background: rgba(10, 14, 22, 0.84); backdrop-filter: blur(12px); box-shadow: 0 8px 30px rgba(0, 0, 0, 0.28); }
.dock-label { margin-right: 3px; color: #7d8ba1; font-size: 10px; letter-spacing: 0.08em; }
.layout-dock button { width: 25px; height: 24px; border: 0; border-radius: 5px; background: transparent; color: #7d8ba1; font: 600 11px var(--font-mono); cursor: pointer; }
.layout-dock button.active { background: #5b8cff; color: #fff; }
.dock-current { min-width: 44px; margin-left: 3px; color: #aab8cc; font-size: 10px; }
.dock-back { margin-left: 7px; padding-left: 8px; border-left: 1px solid rgba(125, 139, 161, 0.2); color: #7d8ba1; font-size: 10px; text-decoration: none; }
.dock-back:hover { color: #e9eef6; }
@keyframes pulse { 0%, 100% { opacity: 0.35; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1); } }
</style>

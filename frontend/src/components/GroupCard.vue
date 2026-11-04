// GroupCard.vue — 策略组卡片：状态/进程概览，可展开懒加载进程列表（总览/策略页共用）。
<script setup lang="ts">
import { ref } from 'vue';
import { ChevronDown, ChevronUp } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { ProcessInfo, Runner } from '@/api/types';
import { fromNow } from '@/utils/format';
import HeartbeatGrid from './HeartbeatGrid.vue';
import NavSparkline from './NavSparkline.vue';
import ProcessTable from './ProcessTable.vue';
import StatusDot from './StatusDot.vue';
import StatusTag from './StatusTag.vue';

const props = withDefaults(defineProps<{ runner: Runner; expandable?: boolean; defaultExpanded?: boolean }>(), {
  expandable: true,
  defaultExpanded: false,
});

const expanded = ref(props.defaultExpanded);
const processes = ref<ProcessInfo[]>([]);
const loaded = ref(false);
const loading = ref(false);
const error = ref('');

async function loadProcesses(): Promise<void> {
  if (loaded.value) return;
  loading.value = true;
  error.value = '';
  try {
    const detail = await api.runner(props.runner.id);
    processes.value = detail.processes;
    loaded.value = true;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '进程加载失败';
  } finally {
    loading.value = false;
  }
}

async function toggle(): Promise<void> {
  expanded.value = !expanded.value;
  if (expanded.value) await loadProcesses();
}

defineExpose({ reload: () => { loaded.value = false; if (expanded.value) void loadProcesses(); } });
</script>

<template>
  <article class="group-card card">
    <div class="head">
      <div class="title-wrap">
        <StatusDot :status="runner.status" :size="7" :pulse="runner.status === 'running'" />
        <router-link :to="'/strategies/' + runner.id" class="name truncate" :title="runner.name">{{ runner.name }}</router-link>
        <StatusTag :status="runner.status" compact />
      </div>
      <div class="head-right">
        <span v-if="runner.process_count" class="proc-count mono" :title="'进程在线 / 进程总数'">
          {{ runner.online_processes }}/{{ runner.process_count }} 进程在线
        </span>
        <button
          v-if="expandable && runner.process_count > 0"
          type="button"
          class="expand"
          :aria-expanded="expanded"
          :aria-label="(expanded ? '收起' : '展开') + runner.name + '进程'"
          @click="toggle"
        >
          <ChevronUp v-if="expanded" :size="14" />
          <ChevronDown v-else :size="14" />
        </button>
      </div>
    </div>

    <div class="nav-row">
      <div class="nav-main">
        <span class="nav-label">策略净值</span>
        <strong class="nav-value mono">{{ runner.nav ?? '—' }}</strong>
        <span v-if="runner.equity" class="nav-equity">权益 ¥{{ runner.equity }}</span>
      </div>
      <NavSparkline v-if="runner.nav_sparkline && runner.nav_sparkline.length" :values="runner.nav_sparkline" />
      <span v-if="runner.nav_updated_at" class="nav-time">更新 {{ fromNow(runner.nav_updated_at) }}</span>
    </div>

    <p class="desc" :title="runner.description || ''">{{ runner.description || '暂无简介' }}</p>

    <div class="meta">
      <span class="meta-item hb-meta">
        <HeartbeatGrid :status="runner.status" :last-seen="runner.last_seen" />
        <span>最后心跳 <span class="mono">{{ runner.last_seen ? fromNow(runner.last_seen) : '从未上报' }}</span></span>
      </span>
      <span v-if="runner.last_msg" class="meta-item msg truncate" :title="runner.last_msg">最后消息：{{ runner.last_msg }}</span>
    </div>

    <div v-if="expanded" class="sub">
      <div v-if="loading" class="sub-loading">
        <div class="skel skel-line" style="height: 22px; margin-bottom: 8px" />
        <div class="skel skel-line" style="height: 22px; width: 70%" />
      </div>
      <div v-else-if="error" class="error-bar">
        <span class="dot" />{{ error }}
        <n-button text size="tiny" @click="loadProcesses">重试</n-button>
      </div>
      <ProcessTable v-else :processes="processes" empty-text="该策略组还没有进程上报；进程首次上报后自动出现。" />
      <router-link :to="'/strategies/' + runner.id" class="detail-link">查看策略详情 →</router-link>
    </div>
  </article>
</template>

<style scoped>
.group-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: inherit;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
  max-width: 260px;
}
.name:hover {
  color: var(--primary);
}
.head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.proc-count {
  font-size: 11px;
  color: var(--text-3);
  white-space: nowrap;
}
.expand {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
}
.expand:hover {
  border-color: var(--border-strong);
  color: var(--text);
}
.desc {
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.6;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.nav-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(91, 140, 255, 0.08), rgba(21, 28, 44, 0.35));
}
.nav-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.nav-label {
  font-size: 10px;
  color: var(--text-3);
}
.nav-value {
  font-size: 19px;
  color: var(--text);
  font-weight: 600;
  letter-spacing: -0.02em;
}
.nav-equity {
  margin-left: 4px;
  font-size: 10px;
  color: var(--text-3);
}
.nav-time {
  margin-left: auto;
  font-size: 10px;
  color: var(--text-3);
  white-space: nowrap;
}
.hb-meta {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--text-3);
}
.msg {
  color: #f5a524;
  max-width: 100%;
}
.sub {
  margin-top: 6px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sub-loading {
  padding: 4px 0;
}
.detail-link {
  align-self: flex-start;
  font-size: 11px;
  color: var(--text-2);
}
.detail-link:hover {
  color: var(--primary);
}
</style>
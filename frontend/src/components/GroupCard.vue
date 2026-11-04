<script setup lang="ts">
// GroupCard.vue — 策略卡片：权益/曲线分层展示，进程健康一眼可见。
import { computed, ref } from 'vue';
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { ProcessInfo, Runner } from '@/api/types';
import { fmtNumber, fromNow } from '@/utils/format';
import HeartbeatGrid from './HeartbeatGrid.vue';
import NavSparkline from './NavSparkline.vue';
import ProcessTable from './ProcessTable.vue';
import StatusDot from './StatusDot.vue';
import StatusTag from './StatusTag.vue';

const props = withDefaults(defineProps<{ runner: Runner; expandable?: boolean }>(), { expandable: true });
const expanded = ref(false);
const processes = ref<ProcessInfo[]>([]);
const loaded = ref(false);
const loading = ref(false);
const error = ref('');
const issueCount = computed(() => Math.max(0, (props.runner.process_count || 0) - (props.runner.online_processes || 0)));

async function loadProcesses(): Promise<void> {
  if (loaded.value) return;
  loading.value = true;
  error.value = '';
  try {
    processes.value = (await api.runner(props.runner.id)).processes;
    loaded.value = true;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '进程加载失败';
  } finally {
    loading.value = false;
  }
}
async function toggle(): Promise<void> {
  if (props.runner.process_count <= 1) return;
  expanded.value = !expanded.value;
  if (expanded.value) await loadProcesses();
}
defineExpose({ reload: () => { loaded.value = false; if (expanded.value) { void loadProcesses(); } } });
</script>

<template>
  <article class="group-card">
    <header class="card-head">
      <div class="identity">
        <StatusDot :status="runner.status" :size="7" :pulse="runner.status === 'running'" />
        <router-link :to="'/strategies/' + runner.id" class="name truncate" :title="runner.name">{{ runner.name }}</router-link>
        <StatusTag :status="runner.status" compact />
      </div>
      <div class="head-right">
        <span v-if="issueCount" class="issue"><AlertTriangle :size="11" />{{ issueCount }} 个进程异常</span>
        <span v-else-if="runner.process_count > 1" class="proc-count">{{ runner.process_count }} 个进程</span>
        <button
          v-if="expandable && runner.process_count > 1"
          type="button"
          class="expand"
          :aria-expanded="expanded"
          aria-label="展开进程"
          @click="toggle"
        >
          <ChevronUp v-if="expanded" :size="14" />
          <ChevronDown v-else :size="14" />
        </button>
      </div>
    </header>

    <div class="equity-area">
      <div class="equity-copy">
        <span class="equity-label">策略权益</span>
        <strong class="equity-value mono">{{ runner.equity ? '¥' + fmtNumber(runner.equity, 2) : '—' }}</strong>
      </div>
      <div class="spark-wrap">
        <NavSparkline v-if="runner.equity_sparkline && runner.equity_sparkline.length" :values="runner.equity_sparkline" :width="150" :height="38" />
      </div>
    </div>

    <div class="health-row">
      <HeartbeatGrid :status="runner.status" :last-seen="runner.last_seen" />
      <span class="health-text">{{ runner.last_seen ? '最后心跳 ' + fromNow(runner.last_seen) : '从未上报' }}</span>
    </div>

    <p class="desc truncate">{{ runner.last_msg ? '最后消息 · ' + runner.last_msg : runner.description || '暂无消息' }}</p>

    <div v-if="expanded" class="sub">
      <div v-if="loading" class="sub-loading">加载进程…</div>
      <div v-else-if="error" class="error-bar"><span class="dot" />{{ error }}</div>
      <ProcessTable v-else :processes="processes" empty-text="还没有进程上报。" />
    </div>
  </article>
</template>

<style scoped>
.group-card {
  display: flex;
  flex-direction: column;
  padding: 15px 16px 13px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, rgba(28, 37, 57, 0.68), rgba(16, 22, 35, 0.72));
  transition: border-color 160ms ease, transform 160ms ease;
}
.group-card:hover { border-color: var(--border-strong); transform: translateY(-1px); }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.identity { display: flex; align-items: center; gap: 7px; min-width: 0; }
.name { font-size: 14px; font-weight: 600; color: var(--text); }
.head-right { display: flex; align-items: center; gap: 7px; }
.issue { display: inline-flex; align-items: center; gap: 3px; color: #f5b64b; font-size: 10px; }
.proc-count { color: var(--text-3); font-size: 10px; }
.expand { display: grid; place-items: center; width: 22px; height: 22px; border: 1px solid var(--border); border-radius: 6px; background: transparent; color: var(--text-3); cursor: pointer; }
.expand:hover { color: var(--text); border-color: var(--border-strong); }
.equity-area { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; margin-top: 15px; }
.equity-copy { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.equity-label { font-size: 10px; color: var(--text-3); }
.equity-value { font-size: 23px; line-height: 1.15; letter-spacing: -0.03em; color: var(--text); white-space: nowrap; }
.spark-wrap { flex: 0 0 auto; opacity: 0.9; }
.health-row { display: flex; align-items: center; gap: 9px; margin-top: 13px; }
.health-text { color: var(--text-3); font-size: 10px; }
.desc { margin-top: 8px; color: var(--text-3); font-size: 10px; }
.sub { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
.sub-loading { color: var(--text-3); font-size: 10px; }
@media (max-width: 520px) { .equity-value { font-size: 20px; } .spark-wrap { display: none; } }
</style>

// ProcessTable.vue — 进程表：状态 / 最后心跳 / loop；可选停用/恢复操作（v0.2）。
<script setup lang="ts">
import { NButton } from 'naive-ui';
import type { ProcessInfo } from '@/api/types';
import { fromNow } from '@/utils/format';
import EmptyState from './EmptyState.vue';
import HeartbeatGrid from './HeartbeatGrid.vue';
import StatusTag from './StatusTag.vue';

withDefaults(defineProps<{ processes: ProcessInfo[]; busy?: string; actionable?: boolean; emptyText?: string }>(), {
  busy: '',
  actionable: false,
  emptyText: '还没有进程上报。策略进程使用同一 token 首次上报后会自动出现。',
});
const emit = defineEmits<{ retire: [name: string]; activate: [name: string] }>();
</script>

<template>
  <div v-if="processes.length" class="tbl-wrap">
    <table class="tbl tbl--compact">
      <thead>
        <tr>
          <th>进程</th>
          <th>状态</th>
          <th>心跳</th>
          <th>最后心跳</th>
          <th class="th-num">loop</th>
          <th v-if="actionable" class="th-actions">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in processes" :key="p.name" :class="{ 'row-retired': p.retired }">
          <td class="mono cell-strong">{{ p.name }}</td>
          <td><StatusTag :status="p.retired ? 'retired' : p.status" compact /></td>
          <td class="hb-cell"><HeartbeatGrid :status="p.status" :retired="p.retired" :last-seen="p.last_seen" /></td>
          <td class="muted nowrap" :title="p.last_seen || ''">{{ p.last_seen ? fromNow(p.last_seen) : '从未上报' }}</td>
          <td class="td-num mono">{{ p.loop === null || p.loop === undefined ? '—' : p.loop }}</td>
          <td v-if="actionable" class="td-actions">
            <n-button v-if="!p.retired" size="tiny" quaternary :loading="busy === p.name" @click="emit('retire', p.name)">停用</n-button>
            <n-button v-else size="tiny" quaternary :loading="busy === p.name" @click="emit('activate', p.name)">恢复</n-button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <EmptyState v-else compact title="暂无进程" :description="emptyText" />
</template>

<style scoped>
.tbl-wrap {
  overflow: auto;
}
.row-retired td {
  opacity: 0.55;
}
.th-actions,
.td-actions {
  text-align: right;
  white-space: nowrap;
}
</style>

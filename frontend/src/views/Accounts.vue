// Accounts.vue — v0.4 账户页：券商账户卡片（权益无小数、策略数/在线数、权益 sparkline）+ 新建账户。
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { NButton } from 'naive-ui';
import { Plus } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account } from '@/api/types';
import { useRealtimeStore } from '@/stores/realtime';
import { useSettingsStore } from '@/stores/settings';
import AccountCard from '@/components/AccountCard.vue';
import AccountCreateModal from '@/components/AccountCreateModal.vue';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';

const settings = useSettingsStore();
const realtime = useRealtimeStore();

const accounts = ref<Account[]>([]);
const loading = ref(true);
const error = ref('');
const createOpen = ref(false);
let pollTimer: number | undefined;
let reloadTimer: number | undefined;

async function load(initial = false, silent = false): Promise<void> {
  if (initial) loading.value = true;
  error.value = '';
  try {
    accounts.value = (await api.accounts()).items;
  } catch (err) {
    if (!silent) error.value = err instanceof Error ? err.message : '账户列表加载失败';
  } finally {
    loading.value = false;
  }
}

function scheduleReload(): void {
  window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => { void load(false, true); }, 700);
}

watch(() => settings.refreshSeq, () => { void load(false, true); });
watch(() => [realtime.lastAccountChangeAt, realtime.lastProcessChangeAt], scheduleReload);

onMounted(() => {
  void load(true);
  pollTimer = window.setInterval(() => {
    if (!document.hidden) void load(false, true);
  }, 20000);
});

onBeforeUnmount(() => {
  window.clearInterval(pollTimer);
  window.clearTimeout(reloadTimer);
});
</script>

<template>
  <div class="page">
    <PageHeader title="账户">
      <template #extra>
        <n-button type="primary" size="small" @click="createOpen = true">
          <template #icon><Plus :size="14" /></template>
          新建账户
        </n-button>
      </template>
    </PageHeader>

    <div v-if="error" class="error-bar">
      <span class="dot" />{{ error }}
      <n-button text size="tiny" @click="load(true)">重试</n-button>
    </div>

    <div v-if="loading" class="account-grid">
      <div v-for="i in 4" :key="i" class="skel skel-card" style="height: 180px" />
    </div>

    <EmptyState
      v-else-if="!accounts.length"
      title="还没有账户"
      description="账户代表券商资金账户；创建账户后即可为下属策略上报账户权益、查看账户净值曲线。"
    >
      <template #action>
        <n-button size="small" type="primary" @click="createOpen = true">新建账户</n-button>
      </template>
    </EmptyState>

    <div v-else class="account-grid">
      <AccountCard v-for="account in accounts" :key="account.id" :account="account" />
    </div>

    <AccountCreateModal v-model:show="createOpen" @created="load(true)" />
  </div>
</template>

<style scoped>
.account-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--gap);
}
@media (max-width: 1100px) {
  .account-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .account-grid { grid-template-columns: minmax(0, 1fr); }
}
</style>

// Settings.vue — v0.2 设置：钉钉通知渠道（启用/编辑/测试）+ 显示偏好；移除日历/安全伪配置。
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NSwitch, useMessage } from 'naive-ui';
import { BellRing, Pencil, Send } from 'lucide-vue-next';
import type { Channel, TestChannelResult, UpColorScheme } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtDateTime } from '@/utils/format';
import ChannelEditModal from '@/components/ChannelEditModal.vue';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import StatusDot from '@/components/StatusDot.vue';

const store = useSettingsStore();
const message = useMessage();
const busyChannel = ref('');
const testResult = ref<Record<string, TestChannelResult>>({});
const channelModal = ref(false);
const editingChannel = ref<Channel | null>(null);

const settings = computed(() => store.data);
const loading = computed(() => store.loading && !store.data);
const error = computed(() => store.error);

function schemeLabel(scheme: UpColorScheme): string {
  return scheme === 'red_up' ? '红涨绿跌（A股习惯）' : '绿涨红跌（欧美习惯）';
}

async function onToggleChannel(channel: Channel, enabled: boolean): Promise<void> {
  busyChannel.value = channel.id;
  try {
    await store.setChannelEnabled(channel.id, enabled);
    message.success((channel.name || channel.id) + (enabled ? ' 已启用' : ' 已停用'));
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败');
  } finally {
    busyChannel.value = '';
  }
}

async function onTestChannel(channel: Channel): Promise<void> {
  busyChannel.value = channel.id;
  try {
    const result = await store.testChannel(channel.id);
    testResult.value = { ...testResult.value, [channel.id]: result };
    message.success(result.message);
  } catch (err) {
    message.error(err instanceof Error ? err.message : '测试发送失败');
  } finally {
    busyChannel.value = '';
  }
}

function openChannelEdit(channel: Channel): void {
  editingChannel.value = channel;
  channelModal.value = true;
}

async function changeScheme(scheme: UpColorScheme): Promise<void> {
  store.applyScheme(scheme);
  message.success('涨跌配色已切换：' + schemeLabel(scheme));
}

watch(() => store.refreshSeq, () => { void store.load(true); });

onMounted(() => {
  void store.load();
});
</script>

<template>
  <div class="page">
    <PageHeader title="设置" subtitle="钉钉通知渠道 / 显示偏好">
      <template #extra>
        <span class="chip"><StatusDot :status="'running'" :size="6" /> 看门狗服务</span>
      </template>
    </PageHeader>

    <div v-if="loading" class="page">
      <div class="skel" style="height: 48px; border-radius: 10px" />
      <div class="skel" style="height: 320px; border-radius: 12px" />
    </div>

    <div v-else-if="error && !settings" class="card">
      <EmptyState title="设置加载失败" :description="error">
        <template #action><n-button size="small" @click="store.load(true)">重新加载</n-button></template>
      </EmptyState>
    </div>

    <template v-else-if="settings">
      <div v-if="error" class="error-bar"><span class="dot" />{{ error }}</div>

      <section class="card settings-card">
        <div class="section-head">
          <div>
            <h2 class="section-title">钉钉通知渠道</h2>
            <p class="section-sub">access_token 在 Webhook URL 中；消息会自动加机器人关键字前缀 <code>[+]</code>，钉钉机器人安全设置里选“自定义关键字”并填 <code>[+]</code>。</p>
          </div>
          <span class="chip">限流 15 条/分钟（本地令牌桶）</span>
        </div>
        <div v-if="settings.channels.length" class="channel-grid">
          <article v-for="channel in settings.channels" :key="channel.id" class="channel-card">
            <div class="channel-head">
              <div class="channel-title">
                <BellRing :size="15" />
                <span class="name">{{ channel.name }}</span>
                <span class="chip chip--soft mono">钉钉群机器人</span>
              </div>
              <n-switch
                :value="channel.enabled"
                size="small"
                :loading="busyChannel === channel.id"
                @update:value="(value: boolean) => onToggleChannel(channel, value)"
              />
            </div>
            <div class="kv-list">
              <div class="kv-row"><span class="k">Webhook</span><span class="v mono">{{ channel.webhook_masked }}</span></div>
              <div class="kv-row"><span class="k">加签密钥</span><span class="v mono">{{ channel.secret_masked }}</span></div>
              <div class="kv-row"><span class="k">关键字前缀</span><span class="v mono">[+]</span></div>
              <div class="kv-row">
                <span class="k">最近测试</span>
                <span class="v mono">{{ channel.last_test_at ? fmtDateTime(channel.last_test_at) + ' · ' + (channel.last_test_ok ? '成功' : '失败') : '未测试' }}</span>
              </div>
            </div>
            <div class="channel-foot">
              <n-button size="small" @click="openChannelEdit(channel)">
                <template #icon><Pencil :size="13" /></template>
                编辑
              </n-button>
              <n-button size="small" :loading="busyChannel === channel.id" :disabled="!channel.enabled" @click="onTestChannel(channel)">
                <template #icon><Send :size="13" /></template>
                发送测试消息
              </n-button>
              <span v-if="testResult[channel.id]" class="test-ok">已发送 · {{ testResult[channel.id].latency_ms ?? 0 }}ms</span>
              <span v-else-if="!channel.enabled" class="faint">渠道已停用</span>
            </div>
          </article>
        </div>
        <EmptyState v-else compact title="暂无通知渠道" description="后端未下发渠道配置。" />
        <p class="section-note">Webhook 与加签密钥保存后不再回显，页面只展示掩码；测试发送会向该渠道发一条测试消息。</p>
      </section>

      <section class="card settings-card">
        <div class="section-head">
          <div>
            <h2 class="section-title">显示偏好</h2>
            <p class="section-sub">颜色仅影响动态中的方向标签（做多/做空）；偏好保存在本机浏览器。</p>
          </div>
        </div>
        <div class="pref-row">
          <div>
            <span class="pref-name">涨跌配色</span>
            <span class="pref-desc">当前 {{ schemeLabel(store.upColorScheme) }}</span>
          </div>
          <div class="seg">
            <button type="button" :class="{ active: store.upColorScheme === 'red_up' }" @click="changeScheme('red_up')">红涨绿跌</button>
            <button type="button" :class="{ active: store.upColorScheme === 'green_up' }" @click="changeScheme('green_up')">绿涨红跌</button>
          </div>
        </div>
      </section>
    </template>

    <ChannelEditModal v-model:show="channelModal" :channel="editingChannel" />
  </div>
</template>

<style scoped>
.settings-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.section-sub {
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.65;
}
.section-note {
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.65;
}
.channel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.channel-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(21, 28, 44, 0.45);
}
.channel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.channel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--primary);
  min-width: 0;
}
.channel-title .name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.kv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kv-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 12px;
}
.kv-row .k {
  width: 76px;
  flex: none;
  color: var(--text-3);
  font-size: 11px;
}
.kv-row .v {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-2);
  word-break: break-all;
}
.channel-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.test-ok {
  font-size: 11px;
  color: var(--down);
}
.pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.pref-name {
  display: block;
  font-size: 12px;
  color: var(--text);
}
.pref-desc {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-3);
}
@media (max-width: 899px) {
  .channel-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>

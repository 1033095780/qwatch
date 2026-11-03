<script setup lang="ts">
// Settings.vue — 设置：通知渠道（钉钉编辑/测试）、交易日历、安全、关于 + 涨跌配色。
import { computed, onMounted, ref, watch } from 'vue';
import { NButton, NSwitch, NTooltip, useMessage } from 'naive-ui';
import { BellRing, Pencil, Send, ShieldCheck } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Channel, TestChannelResult, UpColorScheme } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';
import { fmtDateTime } from '@/utils/format';
import ChannelEditModal from '@/components/ChannelEditModal.vue';
import EmptyState from '@/components/EmptyState.vue';
import PageHeader from '@/components/PageHeader.vue';
import StatusDot from '@/components/StatusDot.vue';
import TabBar from '@/components/TabBar.vue';
import type { TabItem } from '@/components/TabBar.vue';

const store = useSettingsStore();
const message = useMessage();
const tab = ref('channels');
const busyChannel = ref('');
const testResult = ref<Record<string, TestChannelResult>>({});

const channelModal = ref(false);
const editingChannel = ref<Channel | null>(null);

const tabs: TabItem[] = [
  { key: 'channels', label: '通知渠道' },
  { key: 'calendars', label: '交易日历' },
  { key: 'security', label: '安全' },
  { key: 'about', label: '关于' },
];

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
  await store.saveScheme(scheme);
  message.success('涨跌配色已切换：' + schemeLabel(scheme));
}

watch(() => store.refreshSeq, () => {
  store.load(true);
});

onMounted(() => {
  store.load();
});
</script>

<template>
  <div class="page">
    <PageHeader title="设置" subtitle="通知渠道 / 交易日历 / 安全 / 关于">
      <template #extra>
        <span class="chip"><StatusDot status="running" :size="6" /> 服务正常</span>
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

      <section class="card tabs-card">
        <TabBar v-model="tab" :tabs="tabs" />

        <!-- 通知渠道 -->
        <div v-show="tab === 'channels'" class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">钉钉通知渠道</h2>
              <p class="panel-sub">access_token 在 Webhook URL 中；开启加签时填 SEC 开头的密钥。密钥与 token 均脱敏展示，保存后刷新掩码。</p>
            </div>
            <span class="chip">限流 15 条/分钟（本地令牌桶）</span>
          </div>
          <div class="channel-grid">
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
                <div class="kv-row"><span class="k">@手机号</span><span class="v mono">{{ channel.at_mobiles.length ? channel.at_mobiles.join('、') : '未配置' }}</span></div>
                <div class="kv-row"><span class="k">限流</span><span class="v mono">{{ channel.rate_limit_per_min }} 条/分钟</span></div>
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
                <span v-if="testResult[channel.id]" class="test-ok">
                  已发送 · {{ testResult[channel.id].latency_ms }}ms
                </span>
                <span v-else-if="!channel.enabled" class="faint">渠道已停用</span>
              </div>
            </article>
          </div>
          <p class="panel-note">Webhook 与加签密钥保存后不再回显，页面只展示掩码；测试发送会向该渠道发一条测试消息。</p>
        </div>

        <!-- 交易日历 -->
        <div v-show="tab === 'calendars'" class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">交易日历</h2>
              <p class="panel-sub">watchdog 按「交易日 + 时段」判活；夜盘归属下一交易日，非交易时段不误报</p>
            </div>
          </div>
          <div class="calendar-grid">
            <article v-for="cal in settings.calendars" :key="cal.id" class="calendar-card">
              <div class="calendar-head">
                <span class="cal-name">{{ cal.name }}</span>
                <span v-if="cal.night" class="chip night">含夜盘</span>
                <span v-else class="chip">无夜盘</span>
              </div>
              <div class="cal-meta mono">{{ cal.id }} · {{ cal.timezone }}</div>
              <div class="sessions">
                <span v-for="session in cal.sessions" :key="session" class="session mono">{{ session }}</span>
              </div>
              <div class="cal-holidays">
                节假日：{{ cal.holidays === 'cn_a' ? 'A股节假日表' : '期货节假日表' }}（周末调休不开市）
              </div>
            </article>
          </div>
          <p class="panel-note">开盘宽限 5 分钟、收盘宽限 15 分钟；服务重启 60s 内不判死。完整配置由后端 YAML 提供。</p>
        </div>

        <!-- 安全 -->
        <div v-show="tab === 'security'" class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">安全</h2>
              <p class="panel-sub">登录与会话安全</p>
            </div>
            <span class="chip"><ShieldCheck :size="12" /> 单用户 · 单机</span>
          </div>
          <div class="security-list">
            <div class="sec-row">
              <div>
                <span class="sec-name">登录会话有效期</span>
                <span class="sec-desc">会话凭证保存在浏览器；接入后端后改为 HttpOnly session cookie</span>
              </div>
              <span class="mono">{{ settings.security.session_hours }} 小时</span>
            </div>
            <div class="sec-row">
              <div>
                <span class="sec-name">登录限流</span>
                <span class="sec-desc">5 次/分钟/IP + 指数锁定</span>
              </div>
              <span class="mono">{{ settings.security.login_rate_limit }}</span>
            </div>
            <div class="sec-row">
              <div>
                <span class="sec-name">二次验证（TOTP）</span>
                <span class="sec-desc">v0.3 规划能力，当前未启用</span>
              </div>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <span class="disabled-wrap"><n-button size="small" disabled>启用 TOTP</n-button></span>
                </template>
                后端阶段提供 TOTP 绑定与恢复码
              </n-tooltip>
            </div>
            <div class="sec-row">
              <div>
                <span class="sec-name">修改访问密码</span>
                <span class="sec-desc">使用 Argon2id 哈希存储密码</span>
              </div>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <span class="disabled-wrap"><n-button size="small" disabled>修改密码</n-button></span>
                </template>
                后端阶段提供密码修改
              </n-tooltip>
            </div>
          </div>
          <p class="panel-note">
            真实方案：Argon2id 密码哈希；登录成功发 HttpOnly + Secure + SameSite=Lax session cookie；5 次/分钟/IP 限流 + 指数锁定；
            CSRF token；全站 HTTPS + HSTS + CSP + X-Frame-Options；可选 TOTP 二次验证。
          </p>
        </div>

        <!-- 关于 -->
        <div v-show="tab === 'about'" class="panel">
          <div class="panel-head">
            <div>
              <h2 class="panel-title">关于 qwatch</h2>
              <p class="panel-sub">多策略 / 多市场 / 多账户监控工作台</p>
            </div>
          </div>
          <div class="about-grid">
            <div class="about-item"><span class="k">版本</span><span class="v mono">{{ settings.about.version }}</span></div>
            <div class="about-item"><span class="k">构建</span><span class="v mono">{{ settings.about.build }}</span></div>
            <div class="about-item"><span class="k">模式</span><span class="v">{{ settings.about.mode }}</span></div>
            <div class="about-item"><span class="k">License</span><span class="v mono">{{ settings.about.license }}</span></div>
            <div class="about-item"><span class="k">用户</span><span class="v mono">{{ settings.user.name }} · {{ settings.user.role }}</span></div>
            <div class="about-item"><span class="k">时区</span><span class="v mono">Asia/Shanghai（展示）· UTC（存储）</span></div>
          </div>

          <h3 class="sub-title">显示偏好</h3>
          <div class="pref-row">
            <div>
              <span class="sec-name">涨跌配色</span>
              <span class="sec-desc">全站盈亏数字与成交方向：当前 {{ schemeLabel(store.upColorScheme) }}</span>
            </div>
            <div class="seg">
              <button type="button" :class="{ active: store.upColorScheme === 'red_up' }" @click="changeScheme('red_up')">红涨绿跌</button>
              <button type="button" :class="{ active: store.upColorScheme === 'green_up' }" @click="changeScheme('green_up')">绿涨红跌</button>
            </div>
          </div>

          <p class="panel-note">
            前端：Vue 3 + TypeScript + Vite + Naive UI + ECharts + Pinia + Vue Router；
            接口按契约以真实 HTTP 提供，后端接入后无需改动页面。
          </p>
        </div>
      </section>
    </template>
    <ChannelEditModal v-model:show="channelModal" :channel="editingChannel" />
  </div>
</template>

<style scoped>
.tabs-card {
  padding-top: 4px;
}
.panel {
  padding: 18px 0 4px;
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
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kv-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.kv-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-size: 11px;
}
.kv-row .k {
  width: 68px;
  flex: none;
  color: var(--text-3);
}
.kv-row .v {
  color: var(--text-2);
  word-break: break-all;
  font-size: 11px;
}
.channel-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.test-ok {
  font-size: 11px;
  color: #2ecc8f;
}
.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.token-loading {
  padding: 8px 0;
}
.token-note {
  display: block;
  margin-top: 2px;
  font-size: 10px;
  color: var(--text-3);
  font-weight: 400;
}
.tbl .chip {
  margin-right: 4px;
}
.token-status {
  font-size: 11px;
  color: #2ecc8f;
}
.token-status.revoked {
  color: var(--text-3);
}
.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.panel-note {
  margin-top: 16px;
  font-size: 11px;
  line-height: 1.8;
  color: var(--text-3);
}
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.calendar-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(21, 28, 44, 0.45);
}
.calendar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.cal-name {
  font-size: 13px;
  font-weight: 500;
}
.cal-meta {
  font-size: 10px;
  color: var(--text-3);
}
.sessions {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.session {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 6px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: rgba(91, 140, 255, 0.07);
  color: #9db9ff;
  font-size: 10px;
}
.cal-holidays {
  font-size: 10px;
  color: var(--text-3);
}
.security-list {
  display: flex;
  flex-direction: column;
}
.sec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 4px;
  border-bottom: 1px solid rgba(30, 38, 55, 0.65);
  font-size: 12px;
}
.sec-row:last-child {
  border-bottom: none;
}
.sec-name {
  display: block;
  font-size: 13px;
  color: var(--text);
}
.sec-desc {
  display: block;
  margin-top: 3px;
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.6;
}
.disabled-wrap {
  display: inline-flex;
}
.about-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}
.about-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  background: var(--surface);
}
.about-item .k {
  font-size: 10px;
  color: var(--text-3);
}
.about-item .v {
  font-size: 12px;
  color: var(--text);
}
.sub-title {
  margin: 22px 0 8px;
  font-size: 13px;
  font-weight: 600;
}
.pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(21, 28, 44, 0.45);
  flex-wrap: wrap;
}
@media (max-width: 1279px) {
  .channel-grid,
  .calendar-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .about-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 899px) {
  .channel-grid,
  .calendar-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .about-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 639px) {
  .about-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>

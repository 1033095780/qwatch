<script setup lang="ts">
// StrategyTokenModal.vue — 策略接入令牌：查看掩码、生成新令牌（只展示一次）、吊销。
import { ref, watch } from 'vue';
import { NButton, NModal, useDialog, useMessage } from 'naive-ui';
import { AlertTriangle, Copy, KeyRound, Plus, RotateCcw, Trash2 } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Runner, StrategyToken } from '@/api/types';
import { fmtDateTime } from '@/utils/format';
import { heartbeatCurl } from '@/utils/integration';

const props = defineProps<{ show: boolean; runner: Runner | null }>();
const emit = defineEmits<{ 'update:show': [value: boolean] }>();

const message = useMessage();
const dialog = useDialog();

const tokens = ref<StrategyToken[]>([]);
const loading = ref(false);
const generating = ref(false);
const error = ref('');
const result = ref<{ token: string; record: StrategyToken } | null>(null);

async function load(): Promise<void> {
  if (!props.runner) return;
  loading.value = true;
  error.value = '';
  try {
    tokens.value = (await api.tokens({ runner_id: props.runner.id })).items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '令牌加载失败';
  } finally {
    loading.value = false;
  }
}

watch(() => props.show, (visible) => {
  if (!visible) return;
  result.value = null;
  load();
});

async function generate(): Promise<void> {
  if (!props.runner) return;
  generating.value = true;
  try {
    result.value = await api.createToken({
      runner_id: props.runner.id,
      name: props.runner.name,
      platform: props.runner.platform,
      markets: [props.runner.market],
      strategy_type: props.runner.strategy_type,
      tags: props.runner.tags,
    });
    message.success('新令牌已生成，请立即保存');
    await load();
  } catch (err) {
    message.error(err instanceof Error ? err.message : '令牌生成失败');
  } finally {
    generating.value = false;
  }
}

function revoke(token: StrategyToken): void {
  dialog.warning({
    title: '吊销令牌',
    content: '吊销后使用该令牌上报心跳与信号的策略将立即失败，且不可恢复。',
    positiveText: '确认吊销',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.revokeToken(token.id);
        message.success('令牌已吊销');
        await load();
      } catch (err) {
        message.error(err instanceof Error ? err.message : '吊销失败');
      }
    },
  });
}

async function copyPrefix(token: StrategyToken): Promise<void> {
  try {
    await navigator.clipboard.writeText(token.token_prefix);
    message.success('已复制令牌前缀（完整令牌仅在生成时展示）');
  } catch {
    message.error('复制失败，请手动选择文本复制');
  }
}

async function copyToken(): Promise<void> {
  if (!result.value) return;
  try {
    await navigator.clipboard.writeText(result.value.token);
    message.success('完整令牌已复制');
  } catch {
    message.error('复制失败，请手动选择文本复制');
  }
}

function close(): void {
  emit('update:show', false);
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="'接入令牌 · ' + (runner?.name || '')"
    style="width: 620px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="result">
      <p class="result-label">新令牌（只显示一次）</p>
      <div class="token-box mono">{{ result.token }}</div>
      <div class="warn">
        <AlertTriangle :size="14" />
        <span>请立即保存。关闭弹窗后无法再次查看完整令牌；旧令牌不会自动失效，如有需要请手动吊销。</span>
      </div>
      <p class="result-label">接入示例（心跳）</p>
      <pre class="code-block mono">{{ heartbeatCurl(result.token, result.record.name) }}</pre>
      <p class="code-note">信号批量上报：POST /api/v1/events，同样使用该 Bearer Token。</p>
    </template>

    <template v-else>
      <p class="modal-note">策略通过 Bearer Token 上报心跳与信号。完整令牌只在生成时展示一次；页面仅保留前缀。</p>
      <div v-if="loading" class="loading-line"><div class="skel skel-line" style="height: 40px" /><div class="skel skel-line" style="height: 40px" /></div>
      <div v-else-if="error" class="error-bar"><span class="dot" />{{ error }}</div>
      <template v-else>
        <div v-if="tokens.length" class="token-list">
          <div v-for="token in tokens" :key="token.id" class="token-row">
            <div class="token-main">
              <span class="mono prefix">{{ token.token_prefix }}</span>
              <span class="chip" :class="token.status === 'active' ? 'active' : 'revoked'">{{ token.status === 'active' ? '有效' : '已吊销' }}</span>
            </div>
            <div class="token-meta">
              <span>创建 {{ fmtDateTime(token.created_at) }}</span>
              <span v-if="token.last_used_at">最近使用 {{ fmtDateTime(token.last_used_at) }}</span>
              <span>请求 {{ token.request_count }}</span>
            </div>
            <div class="token-actions">
              <n-button size="tiny" quaternary :disabled="token.status !== 'active'" @click="copyPrefix(token)">
                <template #icon><Copy :size="12" /></template>
                复制前缀
              </n-button>
              <n-button size="tiny" quaternary :disabled="token.status !== 'active'" @click="revoke(token)">
                <template #icon><Trash2 :size="12" /></template>
                吊销
              </n-button>
            </div>
          </div>
        </div>
        <div v-else class="empty-token">
          <KeyRound :size="18" />
          <span>该策略还没有接入令牌，生成后即可开始上报。</span>
        </div>
      </template>
    </template>

    <template #footer>
      <div class="footer-actions">
        <n-button size="small" @click="close">{{ result ? '我已保存，关闭' : '关闭' }}</n-button>
        <template v-if="result">
          <n-button size="small" @click="copyToken">
            <template #icon><Copy :size="13" /></template>
            复制完整令牌
          </n-button>
        </template>
        <n-button v-else size="small" type="primary" :loading="generating" @click="generate">
          <template #icon><Plus v-if="!tokens.length" :size="13" /><RotateCcw v-else :size="13" /></template>
          {{ tokens.length ? '生成新令牌' : '生成接入令牌' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.modal-note {
  margin: -4px 0 14px;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.7;
}
.loading-line {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.token-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.token-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
.token-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.prefix {
  font-size: 13px;
  color: var(--text);
}
.token-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--text-3);
}
.token-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}
.chip.active {
  color: var(--down);
  border-color: rgba(46, 204, 143, 0.3);
  background: rgba(46, 204, 143, 0.08);
}
.chip.revoked {
  color: var(--text-3);
}
.empty-token {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--text-3);
  font-size: 12px;
}
.result-label {
  font-size: 11px;
  color: var(--text-3);
  margin-bottom: 6px;
}
.token-box {
  padding: 12px 14px;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: #0b1019;
  color: #9db9ff;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
  user-select: all;
}
.warn {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 165, 36, 0.32);
  border-radius: 8px;
  background: rgba(245, 165, 36, 0.08);
  color: #f5b64b;
  font-size: 12px;
  line-height: 1.6;
}
.footer-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.code-block {
  margin: 6px 0 0;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text-2);
  font-size: 11px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}
.code-note {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-3);
}
</style>

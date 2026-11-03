<script setup lang="ts">
// StrategyCreateModal.vue — 新建策略：一步创建 Runner 并自动生成接入令牌；令牌只展示一次。
import { computed, reactive, ref, watch } from 'vue';
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, useMessage } from 'naive-ui';
import type { FormInst, FormRules } from 'naive-ui';
import { AlertTriangle, CheckCircle2, Copy, KeyRound } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, Market, Platform, StrategyToken, StrategyType } from '@/api/types';
import { PLATFORM_OPTIONS, STRATEGY_TYPE_OPTIONS, TOKEN_MARKET_OPTIONS } from '@/utils/catalog';
import { heartbeatCurl } from '@/utils/integration';

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{ 'update:show': [value: boolean]; created: [] }>();

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const submitting = ref(false);
const accounts = ref<Account[]>([]);
const result = ref<{ token: string; record: StrategyToken } | null>(null);

const form = reactive({
  name: '',
  platform: null as Platform | null,
  market: null as Market | null,
  strategyType: null as StrategyType | null,
  accounts: [] as string[],
  tags: '',
});

const rules: FormRules = {
  name: { required: true, message: '策略名称必填', trigger: ['blur', 'input'] },
};

const accountOptions = computed(() => accounts.value.map((a) => ({ label: a.name + '（' + a.id + '）', value: a.id })));
const marketOptions = TOKEN_MARKET_OPTIONS;
const preview = computed(() => (result.value ? heartbeatCurl(result.value.token, result.value.record.name) : ''));

function randomName(): string {
  return 'strategy-' + Math.random().toString(16).slice(2, 6);
}

watch(() => props.show, async (visible) => {
  if (!visible) return;
  form.name = randomName();
  form.platform = null;
  form.market = null;
  form.strategyType = null;
  form.accounts = [];
  form.tags = '';
  result.value = null;
  formRef.value?.restoreValidation();
  if (!accounts.value.length) {
    try {
      accounts.value = (await api.accounts()).items;
    } catch {
      accounts.value = [];
    }
  }
});

function close(): void {
  emit('update:show', false);
}

function parseTags(text: string): string[] {
  const seen = new Set<string>();
  return text.split(/[,，]/).map((t) => t.trim()).filter((t) => t && !seen.has(t) && seen.add(t));
}

async function submit(): Promise<void> {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const tags = parseTags(form.tags);
    const runnerRes = await api.createRunner({
      name: form.name.trim(),
      platform: form.platform ?? '',
      market: form.market ?? '',
      strategy_type: form.strategyType ?? '',
      tags,
      accounts: form.accounts,
    });
    const runner = runnerRes.runner;
    result.value = await api.createToken({
      runner_id: runner.id,
      name: runner.name,
      platform: runner.platform,
      markets: [runner.market],
      strategy_type: runner.strategy_type,
      tags,
    });
    emit('created');
    message.success('策略已创建，请保存接入令牌');
  } catch (err) {
    message.error(err instanceof Error ? err.message : '创建策略失败');
  } finally {
    submitting.value = false;
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
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="result ? '策略创建成功' : '新建策略'"
    style="width: 580px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="!result">
      <p class="modal-note">创建后会立即生成接入令牌；策略保持「离线」状态，收到第一次心跳后自动上线。名称必填，其余可留空。</p>
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" require-mark-placement="right-hanging">
        <n-form-item label="策略名称" path="name">
          <n-input v-model:value="form.name" placeholder="如 螺纹钢趋势" maxlength="40" />
        </n-form-item>
        <div class="form-grid">
          <n-form-item label="量化平台">
            <n-select v-model:value="form.platform" :options="PLATFORM_OPTIONS" clearable placeholder="可选" />
          </n-form-item>
          <n-form-item label="策略类型">
            <n-select v-model:value="form.strategyType" :options="STRATEGY_TYPE_OPTIONS" clearable placeholder="可选" />
          </n-form-item>
          <n-form-item label="市场">
            <n-select v-model:value="form.market" :options="marketOptions" clearable placeholder="可选" />
          </n-form-item>
          <n-form-item label="关联账户">
            <n-select v-model:value="form.accounts" :options="accountOptions" multiple clearable placeholder="可选，可多选" />
          </n-form-item>
        </div>
        <n-form-item label="标签">
          <n-input v-model:value="form.tags" placeholder="逗号分隔，如 夜盘,期货主账户（可选）" />
        </n-form-item>
      </n-form>
    </template>

    <template v-else>
      <div class="result-head"><CheckCircle2 :size="16" /><span>{{ result.record.name }}</span></div>
      <p class="result-label">接入令牌（只显示一次）</p>
      <div class="token-box mono">{{ result.token }}</div>
      <div class="warn">
        <AlertTriangle :size="14" />
        <span>请立即保存。关闭弹窗后无法再次查看完整令牌，只能在策略详情里重新生成。</span>
      </div>
      <p class="result-label">接入示例（心跳）</p>
      <pre class="code-block mono">{{ preview }}</pre>
      <p class="code-note">信号批量上报：POST /api/v1/events，同样使用该 Bearer Token。</p>
    </template>

    <template #footer>
      <div class="footer-actions">
        <template v-if="!result">
          <n-button size="small" @click="close">取消</n-button>
          <n-button size="small" type="primary" :loading="submitting" @click="submit">创建策略</n-button>
        </template>
        <template v-else>
          <n-button size="small" @click="copyToken">
            <template #icon><Copy :size="13" /></template>
            复制完整令牌
          </n-button>
          <n-button size="small" type="primary" @click="close">我已保存，关闭</n-button>
        </template>
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
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}
.result-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 14px;
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
@media (max-width: 639px) {
  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }
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

<script setup lang="ts">
// StrategyCreateModal.vue — 新建策略：名称/市场/平台/简介，创建后自动生成接入令牌。
import { computed, reactive, ref, watch } from 'vue';
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, useMessage } from 'naive-ui';
import type { FormInst, FormRules } from 'naive-ui';
import { AlertTriangle, CheckCircle2, Copy } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { StrategyToken } from '@/api/types';
import { PLATFORM_OPTIONS, TOKEN_MARKET_OPTIONS } from '@/utils/catalog';
import { heartbeatCurl } from '@/utils/integration';

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{ 'update:show': [value: boolean]; created: [] }>();

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const submitting = ref(false);
const result = ref<{ token: string; record: StrategyToken } | null>(null);

const form = reactive({
  name: '',
  market: '',
  platform: '',
  description: '',
});

const rules: FormRules = {
  name: { required: true, message: '策略名称必填', trigger: ['blur', 'input'] },
  market: { required: true, message: '市场必填', trigger: ['blur', 'change'] },
  platform: { required: true, message: '量化平台必填', trigger: ['blur', 'change'] },
};

const marketOptions = TOKEN_MARKET_OPTIONS;
const preview = computed(() => (result.value ? heartbeatCurl(result.value.token, result.value.record.name) : ''));

function randomName(): string {
  return 'strategy-' + Math.random().toString(16).slice(2, 6);
}

watch(() => props.show, (visible) => {
  if (!visible) return;
  form.name = randomName();
  form.market = '';
  form.platform = '';
  form.description = '';
  result.value = null;
  formRef.value?.restoreValidation();
});

function close(): void {
  emit('update:show', false);
}

async function submit(): Promise<void> {
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const runnerRes = await api.createRunner({
      name: form.name.trim(),
      market: form.market.trim(),
      platform: form.platform.trim(),
      description: form.description.trim(),
    });
    const runner = runnerRes.runner;
    result.value = await api.createToken({
      runner_id: runner.id,
      name: runner.name,
      platform: runner.platform,
      markets: [runner.market],
      strategy_type: runner.strategy_type,
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
      <p class="modal-note">创建后立即生成接入令牌；策略保持「离线」，收到第一次心跳后自动上线。名称、市场、平台可直接填写，也可从常用项选择。</p>
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" require-mark-placement="right-hanging">
        <n-form-item label="策略名称" path="name">
          <n-input v-model:value="form.name" placeholder="如 螺纹钢趋势" maxlength="40" />
        </n-form-item>
        <div class="form-grid">
          <n-form-item label="市场" path="market">
            <n-select v-model:value="form.market" :options="marketOptions" filterable tag placeholder="选择或输入，如 期货" />
          </n-form-item>
          <n-form-item label="量化平台" path="platform">
            <n-select v-model:value="form.platform" :options="PLATFORM_OPTIONS" filterable tag placeholder="选择或输入，如 QMT" />
          </n-form-item>
        </div>
        <n-form-item label="简介">
          <n-input
            v-model:value="form.description"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 3 }"
            maxlength="120"
            show-count
            placeholder="一句话说明策略逻辑（可选）"
          />
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
      <p class="code-note">信号批量上报：POST /api/v1/report，同样使用该 Bearer Token。</p>
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
  color: var(--text-2);
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
  color: var(--text-2);
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
  color: var(--text-2);
}
</style>

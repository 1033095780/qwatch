<script setup lang="ts">
// TokenCreateModal.vue — 申请策略接入令牌：单步表单；创建成功后结果态只展示一次完整 token。
import { reactive, ref, watch } from 'vue';
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, useMessage } from 'naive-ui';
import type { FormInst, FormRules } from 'naive-ui';
import { AlertTriangle, Copy, KeyRound } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Market, Platform, StrategyType, TokenCreateResult } from '@/api/types';
import { PLATFORM_OPTIONS, STRATEGY_TYPE_OPTIONS, TOKEN_MARKET_OPTIONS, parseTags } from '@/utils/catalog';

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{ 'update:show': [value: boolean]; created: [] }>();

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const submitting = ref(false);
const result = ref<TokenCreateResult | null>(null);

const form = reactive({
  name: '',
  platform: null as Platform | null,
  markets: [] as Market[],
  strategyType: null as StrategyType | null,
  tags: '',
  note: '',
});

const rules: FormRules = {
  name: { required: true, message: '策略名称必填', trigger: ['blur', 'input'] },
};

function randomName(): string {
  return 'strategy-' + Math.random().toString(16).slice(2, 6);
}

watch(() => props.show, (visible) => {
  if (!visible) return;
  form.name = randomName();
  form.platform = null;
  form.markets = [];
  form.strategyType = null;
  form.tags = '';
  form.note = '';
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
    result.value = await api.createToken({
      name: form.name.trim(),
      platform: form.platform ?? '',
      markets: form.markets,
      strategy_type: form.strategyType ?? '',
      tags: parseTags(form.tags),
      note: form.note.trim(),
    });
    emit('created');
    message.success('令牌创建成功，请立即保存完整令牌');
  } catch (err) {
    message.error(err instanceof Error ? err.message : '令牌创建失败');
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
    :title="result ? '令牌创建成功' : '申请策略接入令牌'"
    style="width: 560px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="!result">
      <p class="modal-note">策略通过 Bearer Token 上报心跳与信号；名称必填，其余用于接入校验与筛选，可留空。</p>
      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" require-mark-placement="right-hanging">
        <n-form-item label="策略名称" path="name">
          <n-input v-model:value="form.name" placeholder="如 strategy-8f3a" maxlength="40" />
        </n-form-item>
        <div class="form-grid">
          <n-form-item label="量化平台">
            <n-select v-model:value="form.platform" :options="PLATFORM_OPTIONS" clearable placeholder="可选" />
          </n-form-item>
          <n-form-item label="策略类型">
            <n-select v-model:value="form.strategyType" :options="STRATEGY_TYPE_OPTIONS" clearable placeholder="可选" />
          </n-form-item>
        </div>
        <n-form-item label="市场">
          <n-select v-model:value="form.markets" :options="TOKEN_MARKET_OPTIONS" multiple clearable placeholder="可选，可多选" />
        </n-form-item>
        <n-form-item label="标签">
          <n-input v-model:value="form.tags" placeholder="逗号分隔，如 夜盘,期货主账户（可选）" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="form.note" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="可选" />
        </n-form-item>
      </n-form>
    </template>

    <template v-else>
      <div class="result-head"><KeyRound :size="16" /><span>{{ result.record.name }}</span></div>
      <p class="result-label">完整令牌</p>
      <div class="token-box mono">{{ result.token }}</div>
      <div class="warn">
        <AlertTriangle :size="14" />
        <span>此令牌只显示一次，请立即保存。关闭弹窗后将无法再次查看，只能重新申请。</span>
      </div>
    </template>

    <template #footer>
      <div class="footer-actions">
        <template v-if="!result">
          <n-button size="small" @click="close">取消</n-button>
          <n-button size="small" type="primary" :loading="submitting" @click="submit">创建令牌</n-button>
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
</style>

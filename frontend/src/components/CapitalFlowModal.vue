<script setup lang="ts">
// CapitalFlowModal.vue — 手工记录入金/出金、重置盈亏基准；策略 SDK 不需要感知资金操作。
import { computed, ref, watch } from 'vue';
import { NButton, NInput, NModal, useDialog, useMessage } from 'naive-ui';
import { ArrowDownToLine, ArrowUpFromLine, RotateCcw, Trash2 } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { CapitalFlow, CapitalSummary, Runner } from '@/api/types';
import { fmtDateTime } from '@/utils/format';

const props = defineProps<{ show: boolean; runner: Runner | null }>();
const emit = defineEmits<{ 'update:show': [value: boolean]; changed: [] }>();

const message = useMessage();
const jumpSuggestion = computed(() => Number(summary.value?.suggested_amount || 0));
const dialog = useDialog();

const summary = ref<CapitalSummary | null>(null);
const loading = ref(false);
const submitting = ref(false);
const resetting = ref(false);
const deletingId = ref<number | null>(null);
const mode = ref<'deposit' | 'withdraw'>('deposit');
const amountText = ref('');
const note = ref('');

async function load(): Promise<void> {
  if (!props.runner) return;
  loading.value = true;
  try {
    summary.value = await api.capital(props.runner.id);
    const suggested = Number(summary.value.suggested_amount || 0);
    if (suggested && !amountText.value) {
      mode.value = suggested > 0 ? 'deposit' : 'withdraw';
      amountText.value = Math.abs(suggested).toFixed(2);
    }
  } catch (err) {
    message.error(err instanceof Error ? err.message : '资金数据加载失败');
  } finally {
    loading.value = false;
  }
}

watch(() => props.show, (visible) => {
  if (!visible) return;
  mode.value = 'deposit';
  amountText.value = '';
  note.value = '';
  load();
});

function close(): void {
  emit('update:show', false);
}

async function submit(): Promise<void> {
  if (!props.runner) return;
  const amount = Number(amountText.value);
  if (!Number.isFinite(amount) || amount <= 0) {
    message.warning('请输入大于 0 的金额');
    return;
  }
  submitting.value = true;
  try {
    const signed = mode.value === 'deposit' ? amount : -amount;
    summary.value = await api.addCapitalFlow(props.runner.id, { amount: signed, note: note.value.trim() || undefined });
    amountText.value = '';
    note.value = '';
    message.success(mode.value === 'deposit' ? '入金已记录' : '出金已记录');
    emit('changed');
  } catch (err) {
    message.error(err instanceof Error ? err.message : '记录失败');
  } finally {
    submitting.value = false;
  }
}

function resetBaseline(): void {
  const runner = props.runner;
  if (!runner) return;
  dialog.warning({
    title: '重置盈亏基准',
    content: '会把当前累计盈亏归零，从当前权益重新计算；历史资金记录保留，可撤销。',
    positiveText: '确认重置',
    negativeText: '取消',
    onPositiveClick: async () => {
      resetting.value = true;
      try {
        summary.value = await api.resetCapital(runner.id);
        message.success('盈亏基准已重置');
        emit('changed');
      } catch (err) {
        message.error(err instanceof Error ? err.message : '重置失败');
      } finally {
        resetting.value = false;
      }
    },
  });
}

function removeFlow(flow: CapitalFlow): void {
  const runner = props.runner;
  if (!runner) return;
  dialog.warning({
    title: '删除资金记录',
    content: '删除后会重新计算累计盈亏，确认删除？',
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      deletingId.value = flow.id;
      try {
        summary.value = await api.deleteCapitalFlow(runner.id, flow.id);
        message.success('已删除');
        emit('changed');
      } catch (err) {
        message.error(err instanceof Error ? err.message : '删除失败');
      } finally {
        deletingId.value = null;
      }
    },
  });
}

function fmtSigned(value: string): string {
  const n = Number(value);
  const abs = Math.abs(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (n > 0 ? '+' : n < 0 ? '-' : '') + '¥' + abs;
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="'资金变动 · ' + (runner?.name || '')"
    style="width: 640px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <p class="modal-note">初始资金自动取第一条权益快照。入金/出金只需填金额，默认按最近一次净值更新生效，曲线会自动抹平这次跳变；策略脚本无需上报资金操作。</p>

    <div v-if="summary && Number(summary.pending_flows)" class="pending-hint">
      已记录资金变动 {{ fmtSigned(summary.pending_flows) }}，等待该策略下一次上报权益后自动生效，不会先扣成亏损。
    </div>
    <div v-if="summary" class="summary-grid">
      <div class="sum-item"><span class="k">初始资金</span><span class="v mono">¥{{ summary.initial_equity }}</span></div>
      <div class="sum-item"><span class="k">净资金调整</span><span class="v mono">{{ fmtSigned(summary.net_flows) }}</span></div>
      <div class="sum-item"><span class="k">累计盈亏</span><span class="v mono" :class="Number(summary.total_pnl) >= 0 ? 'pos' : 'neg'">{{ fmtSigned(summary.total_pnl) }}</span></div>
      <div class="sum-item"><span class="k">今日盈亏</span><span class="v mono" :class="Number(summary.today_pnl) >= 0 ? 'pos' : 'neg'">{{ fmtSigned(summary.today_pnl) }}</span></div>
    </div>

    <div v-if="jumpSuggestion" class="jump-hint">
      检测到最近一次权益跳变 {{ fmtSigned(String(jumpSuggestion)) }}，已按{{ jumpSuggestion > 0 ? '入金' : '出金' }}填好金额，确认即可抹平跳变。
    </div>
    <div class="flow-form">
      <div class="mode-switch">
        <button type="button" :class="{ active: mode === 'deposit' }" @click="mode = 'deposit'">
          <ArrowDownToLine :size="14" /> 入金
        </button>
        <button type="button" :class="{ active: mode === 'withdraw' }" @click="mode = 'withdraw'">
          <ArrowUpFromLine :size="14" /> 出金
        </button>
      </div>
      <div class="form-row">
        <n-input v-model:value="amountText" placeholder="金额" inputmode="decimal" class="amount-input" />
        <n-input v-model:value="note" placeholder="备注（可选）" maxlength="100" class="note-input" />
        <n-button type="primary" :loading="submitting" @click="submit">记录</n-button>
      </div>
    </div>

    <div class="flow-head">
      <span>资金记录</span>
      <n-button size="tiny" quaternary :loading="resetting" @click="resetBaseline">
        <template #icon><RotateCcw :size="12" /></template>
        重置盈亏基准
      </n-button>
    </div>

    <div v-if="loading" class="flow-list">
      <div v-for="i in 3" :key="i" class="skel skel-line" style="height: 34px" />
    </div>
    <div v-else-if="summary && summary.flows.length" class="flow-list">
      <div v-for="flow in summary.flows" :key="flow.id" class="flow-row">
        <span class="flow-ts mono">{{ fmtDateTime(flow.ts) }}</span>
        <span class="flow-amount mono" :class="Number(flow.amount) >= 0 ? 'pos' : 'neg'">{{ fmtSigned(flow.amount) }}</span>
        <span class="flow-kind">{{ flow.kind === 'reset' ? '基准重置' : '资金变动' }}</span>
        <span class="flow-note truncate">{{ flow.note || '—' }}</span>
        <n-button size="tiny" quaternary :loading="deletingId === flow.id" @click="removeFlow(flow)">
          <template #icon><Trash2 :size="12" /></template>
        </n-button>
      </div>
    </div>
    <div v-else class="flow-empty">暂无资金记录。入金/出金后在这里记一笔即可。</div>

    <template #footer>
      <div class="footer-actions">
        <n-button size="small" @click="close">关闭</n-button>
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
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.sum-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.sum-item .k {
  font-size: 10px;
  color: var(--text-2);
}
.sum-item .v {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}
.pos {
  color: var(--up);
}
.neg {
  color: var(--down);
}
.pending-hint {
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(46, 204, 143, .28);
  border-radius: 7px;
  background: rgba(46, 204, 143, .07);
  color: #2ecc8f;
  font-size: 11px;
  line-height: 1.6;
}
.jump-hint {
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(245, 165, 36, .28);
  border-radius: 7px;
  background: rgba(245, 165, 36, .08);
  color: #f5a524;
  font-size: 11px;
  line-height: 1.6;
}
.flow-form {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface-2);
}
.mode-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.mode-switch button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-2);
  font-size: 12px;
  cursor: pointer;
}
.mode-switch button.active {
  border-color: var(--primary);
  background: var(--primary-soft);
  color: var(--text);
}
.form-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr) auto;
  gap: 8px;
}
.flow-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0 8px;
  font-size: 12px;
  color: var(--text-2);
}
.flow-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
}
.flow-row {
  display: grid;
  grid-template-columns: 92px 96px 52px minmax(0, 1fr) 30px;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
}
.flow-ts {
  color: var(--text-2);
}
.flow-amount {
  font-weight: 600;
}
.flow-kind {
  color: var(--text-2);
}
.flow-note {
  color: var(--text-3);
}
.flow-empty {
  padding: 14px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--text-3);
  font-size: 12px;
}
.footer-actions {
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 639px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .form-row {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .note-input {
    grid-column: span 2;
  }
  .flow-row {
    grid-template-columns: 70px 80px 48px minmax(0, 1fr) 30px;
  }
}
</style>

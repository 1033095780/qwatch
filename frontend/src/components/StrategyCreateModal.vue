// StrategyCreateModal.vue — v0.5 新建策略：必须选择已有账户；无账户时可在弹窗内直接创建账户。
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, useMessage } from 'naive-ui';
import type { FormInst, FormRules } from 'naive-ui';
import { AlertTriangle, CheckCircle2, Copy, Plus } from 'lucide-vue-next';
import { api } from '@/api/client';
import type { Account, Runner, StrategyToken } from '@/api/types';
import { reportCurl } from '@/utils/integration';

const props = defineProps<{ show: boolean; accounts?: Account[] }>();
const emit = defineEmits<{ 'update:show': [value: boolean]; created: [] }>();

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const submitting = ref(false);
const loadingAccounts = ref(false);
const accounts = ref<Account[]>(props.accounts ? [...props.accounts] : []);
const creatingAccount = ref(false);
const accountBusy = ref(false);
const accountForm = reactive({ name: '', broker: '' });
const result = ref<{ runner: Runner; token: string; record: StrategyToken } | null>(null);

const form = reactive({ name: '', description: '', account_id: '' });

const accountOptions = computed(() => accounts.value.map((a) => ({ value: a.id, label: a.broker && a.broker !== a.name ? a.broker + ' · ' + a.name : a.name })));
const rules: FormRules = {
  name: { required: true, message: '策略名称必填', trigger: ['blur', 'input'] },
  account_id: { required: true, message: '请选择所属账户', trigger: ['blur', 'change'] },
};
const preview = computed(() => (result.value ? reportCurl(result.value.token) : ''));

function randomName(): string {
  return 'strategy-' + Math.random().toString(16).slice(2, 6);
}

async function loadAccounts(): Promise<void> {
  loadingAccounts.value = true;
  try {
    accounts.value = (await api.accounts()).items;
    if (!accounts.value.length) creatingAccount.value = true;
  } catch {
    accounts.value = [];
    creatingAccount.value = true;
  } finally {
    loadingAccounts.value = false;
  }
}

watch(() => props.show, (visible) => {
  if (!visible) return;
  form.name = randomName();
  form.description = '';
  form.account_id = '';
  result.value = null;
  creatingAccount.value = false;
  accountForm.name = '';
  accountForm.broker = '';
  formRef.value?.restoreValidation();
  if (props.accounts && props.accounts.length) {
    accounts.value = [...props.accounts];
    if (accounts.value.length === 1) form.account_id = accounts.value[0].id;
  } else {
    void loadAccounts();
  }
});

watch(() => props.accounts, (next) => {
  if (next && next.length && !accounts.value.length) accounts.value = [...next];
}, { deep: false });

function close(): void {
  emit('update:show', false);
}

function startCreateAccount(): void {
  creatingAccount.value = true;
  accountForm.name = '';
  accountForm.broker = '';
}

function cancelCreateAccount(): void {
  creatingAccount.value = false;
  if (!accounts.value.length) message.warning('还没有账户，请先创建一个账户');
}

async function createAccountInline(): Promise<void> {
  if (!accountForm.name.trim() || !accountForm.broker.trim()) {
    message.warning('请填写账户名称与券商');
    return;
  }
  accountBusy.value = true;
  try {
    const res = await api.createAccount({ name: accountForm.name.trim(), broker: accountForm.broker.trim() });
    const account = res.account;
    accounts.value = [...accounts.value, account];
    form.account_id = account.id;
    creatingAccount.value = false;
    message.success('账户已创建并选中');
  } catch (err) {
    message.error(err instanceof Error ? err.message : '创建账户失败');
  } finally {
    accountBusy.value = false;
  }
}

async function submit(): Promise<void> {
  if (!form.account_id) {
    message.warning('请选择所属账户（可先创建账户）');
    return;
  }
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const runnerRes = await api.createRunner({
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      account_id: form.account_id,
    });
    const runner = runnerRes.runner;
    const tokenRes = await api.createToken({ runner_id: runner.id, name: runner.name });
    result.value = { runner, token: tokenRes.token, record: tokenRes.record };
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
    style="width: 600px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="!result">
      <p class="modal-note">策略必须属于一个账户；同一策略下的多个进程使用同一个令牌上报，进程首次上报后自动出现。</p>

      <div class="account-block">
        <div class="account-head">
          <span class="account-label">所属账户</span>
          <n-button v-if="!creatingAccount" text size="tiny" type="primary" @click="startCreateAccount">
            <template #icon><Plus :size="12" /></template>
            新建账户
          </n-button>
        </div>
        <n-select
          v-if="!creatingAccount"
          v-model:value="form.account_id"
          :options="accountOptions"
          :loading="loadingAccounts"
          placeholder="选择所属账户"
          class="account-select"
        />
        <div v-else class="account-inline">
          <div class="inline-note"><AlertTriangle :size="13" />还没有账户？在下方创建账户，创建后会自动选中，无需离开当前流程。</div>
          <div class="inline-fields">
            <n-input v-model:value="accountForm.name" placeholder="账户名称，如 国金证券主账户" maxlength="40" />
            <n-input v-model:value="accountForm.broker" placeholder="券商，如 国金证券" maxlength="40" />
          </div>
          <div class="inline-actions">
            <n-button size="small" type="primary" :loading="accountBusy" @click="createAccountInline">创建并选择</n-button>
            <n-button v-if="accounts.length" size="small" @click="cancelCreateAccount">取消</n-button>
          </div>
        </div>
      </div>

      <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" require-mark-placement="right-hanging">
        <n-form-item label="策略名称" path="name">
          <n-input v-model:value="form.name" placeholder="如 螺纹钢趋势" maxlength="40" show-count />
        </n-form-item>
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
      <div class="result-head"><CheckCircle2 :size="16" /><span>{{ result.runner.name }}</span></div>
      <p class="result-label">接入令牌（只显示一次）</p>
      <div class="token-box mono">{{ result.token }}</div>
      <div class="warn">
        <AlertTriangle :size="14" />
        <span>请立即保存。关闭弹窗后无法再次查看完整令牌，只能在策略详情里重新生成。</span>
      </div>
      <p class="result-label">接入示例（心跳）</p>
      <pre class="code-block mono">{{ preview }}</pre>
      <p class="code-note">同一策略的每个进程都必须带自己的 instrument（如 rb / ag / IF）；消息与信号也走 POST /api/v1/report。</p>
    </template>

    <template #footer>
      <div class="footer-actions">
        <template v-if="!result">
          <n-button size="small" @click="close">取消</n-button>
          <n-button size="small" type="primary" :loading="submitting" :disabled="creatingAccount || !form.account_id" @click="submit">创建策略</n-button>
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
.modal-note { margin: -4px 0 14px; font-size: 12px; color: var(--text-2); line-height: 1.7; }
.account-block { margin-bottom: 14px; }
.account-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.account-label { font-size: 12px; color: var(--text-2); }
.account-select { width: 100%; }
.account-inline { padding: 10px 12px; border: 1px dashed var(--border); border-radius: 8px; background: var(--surface); }
.inline-note { display: flex; align-items: flex-start; gap: 6px; color: #f5b64b; font-size: 11px; line-height: 1.6; }
.inline-fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; margin-top: 8px; }
.inline-actions { display: flex; gap: 8px; margin-top: 8px; }
.result-head { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 14px; }
.result-label { font-size: 11px; color: var(--text-2); margin-bottom: 6px; }
.token-box { padding: 12px 14px; border: 1px solid var(--border-strong); border-radius: 8px; background: #0b1019; color: #9db9ff; font-size: 12px; line-height: 1.6; word-break: break-all; user-select: all; }
.warn { display: flex; align-items: flex-start; gap: 8px; margin-top: 12px; padding: 10px 12px; border: 1px solid rgba(245, 165, 36, 0.32); border-radius: 8px; background: rgba(245, 165, 36, 0.08); color: #f5b64b; font-size: 12px; line-height: 1.6; }
.footer-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
.code-block { margin: 6px 0 0; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg); color: var(--text-2); font-size: 11px; line-height: 1.7; white-space: pre-wrap; word-break: break-all; }
.code-note { margin-top: 8px; font-size: 11px; color: var(--text-2); }
@media (max-width: 520px) { .inline-fields { grid-template-columns: minmax(0, 1fr); } }
</style>

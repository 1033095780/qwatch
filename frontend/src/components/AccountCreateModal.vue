// AccountCreateModal.vue — v0.4 新建账户：名称/券商必填，简介可选。
<script setup lang="ts">
import { reactive, ref, watch } from 'vue';
import { NButton, NForm, NFormItem, NInput, NModal, useMessage } from 'naive-ui';
import type { FormInst, FormRules } from 'naive-ui';
import { api } from '@/api/client';

const props = defineProps<{ show: boolean }>();
const emit = defineEmits<{ 'update:show': [value: boolean]; created: [] }>();

const message = useMessage();
const formRef = ref<FormInst | null>(null);
const submitting = ref(false);
const form = reactive({ name: '', broker: '', description: '' });

const rules: FormRules = {
  name: { required: true, message: '账户名称必填', trigger: ['blur', 'input'] },
  broker: { required: true, message: '券商名称必填', trigger: ['blur', 'input'] },
};

watch(() => props.show, (visible) => {
  if (!visible) return;
  form.name = '';
  form.broker = '';
  form.description = '';
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
    await api.createAccount({
      name: form.name.trim(),
      broker: form.broker.trim(),
      description: form.description.trim() || undefined,
    });
    message.success('账户已创建');
    emit('created');
    close();
  } catch (err) {
    message.error(err instanceof Error ? err.message : '创建账户失败');
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="新建账户"
    style="width: 520px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <p class="modal-note">账户代表一个券商资金账户；其下属所有策略进程上报的权益/净值都会更新这个账户。</p>
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" require-mark-placement="right-hanging">
      <n-form-item label="账户名称" path="name">
        <n-input v-model:value="form.name" placeholder="如 国金证券主账户" maxlength="40" show-count />
      </n-form-item>
      <n-form-item label="券商" path="broker">
        <n-input v-model:value="form.broker" placeholder="如 国金证券 / 徽商期货" maxlength="40" show-count />
      </n-form-item>
      <n-form-item label="简介">
        <n-input v-model:value="form.description" type="textarea" :autosize="{ minRows: 2, maxRows: 3 }" maxlength="120" show-count placeholder="账户用途说明（可选）" />
      </n-form-item>
    </n-form>
    <template #footer>
      <div class="footer-actions">
        <n-button size="small" @click="close">取消</n-button>
        <n-button size="small" type="primary" :loading="submitting" @click="submit">创建账户</n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.modal-note { margin: -4px 0 14px; font-size: 12px; color: var(--text-2); line-height: 1.7; }
.footer-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
</style>

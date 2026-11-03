<script setup lang="ts">
// ChannelEditModal.vue — 编辑钉钉群机器人渠道；保存后 PUT /settings 并按掩码刷新。
import { ref, watch } from 'vue';
import { NButton, NForm, NFormItem, NInput, NModal, NSwitch, useMessage } from 'naive-ui';
import type { FormInst, FormRules } from 'naive-ui';
import type { Channel, ChannelPatch } from '@/api/types';
import { useSettingsStore } from '@/stores/settings';

const props = defineProps<{ show: boolean; channel: Channel | null }>();
const emit = defineEmits<{ 'update:show': [value: boolean]; saved: [] }>();

const store = useSettingsStore();
const message = useMessage();
const formRef = ref<FormInst | null>(null);
const saving = ref(false);

const form = ref({
  webhook: '',
  secret: '',
  enabled: true,
});

const rules: FormRules = {
  webhook: [
    { required: true, message: 'Webhook 地址必填', trigger: ['blur', 'input'] },
    {
      validator: (_rule: unknown, value: string) => {
        if (!value) return true;
        const valid = /^https:\/\/oapi\.dingtalk\.com\/robot\/send\?/.test(value) && value.includes('access_token=');
        return valid || new Error('需为 https://oapi.dingtalk.com/robot/send?access_token=... 格式');
      },
      trigger: ['blur', 'input'],
    },
  ],
};

watch(() => props.show, (visible) => {
  if (!visible) return;
  form.value.webhook = '';
  form.value.secret = '';
  form.value.enabled = props.channel?.enabled ?? true;
  formRef.value?.restoreValidation();
});

function close(): void {
  emit('update:show', false);
}

async function submit(): Promise<void> {
  if (!props.channel) return;
  try {
    await formRef.value?.validate();
  } catch {
    return;
  }
  saving.value = true;
  try {
    const patch: ChannelPatch = {
      id: props.channel.id,
      enabled: form.value.enabled,
      webhook: form.value.webhook.trim(),
    };
    patch.secret = form.value.secret.trim();
    await store.saveChannel(patch);
    message.success('渠道配置已保存，密钥已刷新掩码');
    emit('saved');
    close();
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败');
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="编辑钉钉渠道"
    style="width: 560px; max-width: calc(100vw - 32px)"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <p class="modal-note">
      access_token 在 Webhook URL 中；消息会自动加关键字前缀 <code>[+]</code>（钉钉机器人安全设置里选“自定义关键字”并填 <code>[+]</code>）。没有加签就留空密钥；保存后完整值不再回显。
    </p>
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" require-mark-placement="right-hanging">
      <n-form-item label="Webhook 地址" path="webhook">
        <n-input
          v-model:value="form.webhook"
          :placeholder="channel ? '当前：' + channel.webhook_masked + '（请粘贴完整地址）' : 'https://oapi.dingtalk.com/robot/send?access_token=...'"
        />
      </n-form-item>
      <n-form-item label="加签密钥">
        <n-input v-model:value="form.secret" type="password" show-password-on="click" placeholder="没有加签就留空；留空保存会清除旧密钥" />
      </n-form-item>
      <n-form-item label="启用渠道">
        <n-switch v-model:value="form.enabled" />
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer-actions">
        <n-button size="small" @click="close">取消</n-button>
        <n-button size="small" type="primary" :loading="saving" @click="submit">保存配置</n-button>
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
.footer-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
</style>

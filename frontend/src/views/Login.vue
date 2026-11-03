<script setup lang="ts">
// Login.vue — 密码登录；记住我决定 localStorage / sessionStorage；next 回跳。
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NButton, NCheckbox, NInput, useMessage } from 'naive-ui';
import { ArrowRight, LockKeyhole } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth';
import BrandMark from '@/components/BrandMark.vue';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const message = useMessage();

const password = ref('');
const remember = ref(true);
const errorText = ref('');

const nextPath = computed(() => {
  const next = route.query.next;
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : '/overview';
});

async function submit(): Promise<void> {
  errorText.value = '';
  if (!password.value) {
    errorText.value = '请输入访问密码';
    return;
  }
  try {
    await auth.login(password.value, remember.value);
    message.success('登录成功');
    await router.replace(nextPath.value);
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '登录失败';
  }
}
</script>

<template>
  <div class="login-page">
    <div class="bg-grid" aria-hidden="true" />
    <div class="glow glow-a" aria-hidden="true" />
    <div class="glow glow-b" aria-hidden="true" />

    <div class="login-shell">
      <section class="brand-panel">
        <BrandMark size="lg" />
        <h1 class="headline">多策略多市场<br />监控工作台</h1>
        <p class="lede">净值、交易与策略存活，一屏掌握。</p>
      </section>

      <section class="form-panel">
        <div class="form-card">
          <div class="mobile-brand"><BrandMark size="md" /></div>
          <h2 class="form-title">登录</h2>
          <p class="form-sub">使用访问密码进入工作台</p>

          <label class="field-label" for="password">访问密码</label>
          <n-input
            id="password"
            v-model:value="password"
            type="password"
            size="large"
            placeholder="输入访问密码"
            :show-password-on="'click'"
            :input-props="{ autocomplete: 'current-password', autofocus: true, 'aria-label': '访问密码' }"
            @keyup.enter="submit"
          >
            <template #prefix><LockKeyhole :size="15" /></template>
          </n-input>

          <div class="form-row">
            <n-checkbox v-model:checked="remember">记住我</n-checkbox>
          </div>

          <div v-if="errorText" class="error-bar">
            <span class="dot" />{{ errorText }}
          </div>

          <n-button type="primary" size="large" block :loading="auth.loading" class="submit" @click="submit">
            进入面板
            <template #icon><ArrowRight :size="16" /></template>
          </n-button>

        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px;
  overflow: hidden;
  background: var(--bg);
}
.bg-grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(30, 38, 55, 0.32) 1px, transparent 1px),
    linear-gradient(90deg, rgba(30, 38, 55, 0.32) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 70% at 50% 40%, #000 30%, transparent 75%);
  pointer-events: none;
}
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(110px);
  opacity: 0.5;
  pointer-events: none;
}
.glow-a {
  width: 520px;
  height: 520px;
  background: rgba(91, 140, 255, 0.22);
  top: -160px;
  left: -120px;
}
.glow-b {
  width: 420px;
  height: 420px;
  background: rgba(46, 204, 143, 0.12);
  bottom: -180px;
  right: -80px;
}
.login-shell {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 72px;
  align-items: center;
  width: 100%;
  max-width: 1120px;
}
.brand-panel {
  padding: 8px 0;
}
.headline {
  margin: 34px 0 14px;
  font-size: 40px;
  line-height: 1.22;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--text);
}
.lede {
  max-width: 420px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-2);
}
.features {
  list-style: none;
  margin: 34px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 420px;
}
.features li {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  color: var(--primary);
}
.features li div {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.f-title {
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
}
.f-desc {
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
}
.panel-foot {
  margin-top: 48px;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--text-3);
}
.form-card {
  width: 100%;
  max-width: 380px;
  margin-left: auto;
  padding: 32px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(16, 22, 36, 0.82);
  backdrop-filter: blur(14px);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.32);
}
.mobile-brand {
  display: none;
  margin-bottom: 20px;
}
.form-title {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.form-sub {
  margin-top: 4px;
  margin-bottom: 24px;
  font-size: 12px;
  color: var(--text-2);
}
.field-label {
  display: block;
  margin-bottom: 7px;
  font-size: 12px;
  color: var(--text-2);
}
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 14px 0 18px;
  font-size: 12px;
}
.demo-pwd {
  font-size: 11px;
  color: var(--text-3);
}
.error-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid rgba(240, 68, 56, 0.35);
  background: rgba(240, 68, 56, 0.08);
  color: #ffb4ad;
  font-size: 12px;
}
.error-bar .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f04438;
  flex: none;
}
.submit {
  margin-top: 4px;
}
.demo-note {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.7;
}
.tag {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(245, 165, 36, 0.12);
  border: 1px solid rgba(245, 165, 36, 0.26);
  color: #f5b64b;
  font-size: 10px;
}
@media (max-width: 899px) {
  .login-shell {
    grid-template-columns: minmax(0, 1fr);
    max-width: 400px;
    gap: 0;
  }
  .brand-panel {
    display: none;
  }
  .form-card {
    margin: 0 auto;
  }
  .mobile-brand {
    display: block;
  }
}
@media (max-width: 639px) {
  .login-page {
    padding: 16px;
  }
  .form-card {
    padding: 24px;
  }
}
</style>

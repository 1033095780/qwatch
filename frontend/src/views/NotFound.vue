<script setup lang="ts">
// NotFound.vue — 404：返回总览（未登录则回登录）。
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { NButton } from 'naive-ui';
import { ArrowLeft } from 'lucide-vue-next';
import { useAuthStore } from '@/stores/auth';
import BrandMark from '@/components/BrandMark.vue';

const router = useRouter();
const auth = useAuthStore();
const backTo = computed(() => (auth.isAuthenticated ? '/overview' : '/login'));
</script>

<template>
  <div class="nf-page">
    <div class="glow" aria-hidden="true" />
    <div class="nf-card">
      <BrandMark size="md" />
      <p class="code mono">404</p>
      <h1 class="title">页面不存在</h1>
      <p class="desc">你访问的地址可能已下线，或链接拼写有误。检查一下地址栏，或回到面板继续。</p>
      <div class="actions">
        <n-button type="primary" @click="router.replace(backTo)">
          <template #icon><ArrowLeft :size="15" /></template>
          {{ auth.isAuthenticated ? '返回总览' : '前往登录' }}
        </n-button>
        <n-button quaternary @click="router.back()">返回上一页</n-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nf-page {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  overflow: hidden;
}
.glow {
  position: absolute;
  width: 560px;
  height: 560px;
  border-radius: 50%;
  background: rgba(91, 140, 255, 0.14);
  filter: blur(120px);
  pointer-events: none;
}
.nf-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 460px;
  padding: 36px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(16, 22, 36, 0.8);
  backdrop-filter: blur(12px);
}
.code {
  margin: 26px 0 6px;
  font-size: 64px;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--primary);
  line-height: 1;
  opacity: 0.85;
}
.title {
  font-size: 22px;
  font-weight: 600;
}
.desc {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-2);
  line-height: 1.75;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 26px;
  flex-wrap: wrap;
}
</style>

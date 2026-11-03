// main.ts — 应用入口：pinia + router + 全局样式；401 时清理登录态并跳登录。
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { useAuthStore } from './stores/auth';
import './styles/tokens.css';
import './styles/global.css';

// 涨跌配色在首屏渲染前应用，避免闪色
try {
  const scheme = localStorage.getItem('qwatch.updown');
  document.documentElement.dataset.upScheme = scheme === 'green_up' ? 'green_up' : 'red_up';
} catch {
  document.documentElement.dataset.upScheme = 'red_up';
}

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
app.use(router);

window.addEventListener('qwatch:unauthorized', () => {
  const auth = useAuthStore(pinia);
  if (!auth.isAuthenticated) return;
  auth.logout(false);
  const current = router.currentRoute.value;
  if (current.name !== 'login') {
    router.replace({ path: '/login', query: { next: current.fullPath } });
  }
});

app.mount('#app');

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
  // token 可能已经在 fetchMe 中被清掉；这里不能因为 isAuthenticated=false 就提前返回。
  const auth = useAuthStore(pinia);
  auth.logout(false);
  const current = router.currentRoute.value;
  if (current.name !== 'login') {
    // 直接整页跳转，避免过期页面先渲染出错误条再慢慢切路由。
    const next = encodeURIComponent(current.fullPath);
    window.location.replace('/login?next=' + next);
  }
});

app.mount('#app');

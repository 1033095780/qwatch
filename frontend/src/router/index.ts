// router/index.ts — 11 条路由：登录、业务 9 页、404；未登录守卫带 next 回跳。
import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

declare module 'vue-router' {
  interface RouteMeta {
    title?: string;
    public?: boolean;
    parent?: { title: string; to: string };
  }
}

const AppShell = () => import('@/layouts/AppShell.vue');

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', redirect: '/overview' },
        { path: 'overview', name: 'overview', component: () => import('@/views/Overview.vue'), meta: { title: '总览' } },
        { path: 'strategies', name: 'strategies', component: () => import('@/views/Strategies.vue'), meta: { title: '策略' } },
        {
          path: 'strategies/:id', name: 'strategy-detail', component: () => import('@/views/StrategyDetail.vue'),
          meta: { title: '策略详情', parent: { title: '策略', to: '/strategies' } },
        },
        { path: 'accounts', name: 'accounts', component: () => import('@/views/Accounts.vue'), meta: { title: '账户' } },
        {
          path: 'accounts/:id', name: 'account-detail', component: () => import('@/views/AccountDetail.vue'),
          meta: { title: '账户详情', parent: { title: '账户', to: '/accounts' } },
        },
        { path: 'trades', name: 'trades', component: () => import('@/views/Trades.vue'), meta: { title: '交易流水' } },
        { path: 'alerts', name: 'alerts', component: () => import('@/views/Alerts.vue'), meta: { title: '告警中心' } },
        { path: 'reports', name: 'reports', component: () => import('@/views/Reports.vue'), meta: { title: '日报' } },
        { path: 'settings', name: 'settings', component: () => import('@/views/Settings.vue'), meta: { title: '设置' } },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFound.vue'),
      meta: { title: '页面不存在', public: true },
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  document.title = (to.meta.title ? to.meta.title + ' · ' : '') + 'qwatch 监控工作台';
  if (!to.meta.public && !auth.isAuthenticated) {
    return { path: '/login', query: { next: to.fullPath } };
  }
  if (to.name === 'login' && auth.isAuthenticated) {
    const next = typeof to.query.next === 'string' && to.query.next.startsWith('/') && !to.query.next.startsWith('//')
      ? to.query.next
      : '/overview';
    return next;
  }
  return true;
});

export default router;

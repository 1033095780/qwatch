// router/index.ts — v0.5：4 个一级页面（总览/策略/告警/设置）+ 策略详情 + 登录/404；旧链接重定向。
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
          path: 'accounts/:id', name: 'account-detail', component: () => import('@/views/AccountDetail.vue'),
          meta: { title: '账户详情', parent: { title: '策略', to: '/strategies' } },
        },
        {
          path: 'strategies/:id', name: 'strategy-detail', component: () => import('@/views/StrategyDetail.vue'),
          meta: { title: '策略详情', parent: { title: '策略', to: '/strategies' } },
        },
        { path: 'activity', name: 'activity', component: () => import('@/views/Activity.vue'), meta: { title: '动态' } },
        { path: 'settings', name: 'settings', component: () => import('@/views/Settings.vue'), meta: { title: '设置' } },
        // 已下线页面：保留重定向，避免旧书签 404
        { path: 'alerts', redirect: '/activity' },
        { path: 'accounts', redirect: '/strategies' },
        { path: 'signals', redirect: '/overview' },
        { path: 'trades', redirect: '/overview' },
        { path: 'reports', redirect: '/overview' },
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

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  document.title = (to.meta.title ? to.meta.title + ' · ' : '') + 'qwatch 监控工作台';
  if (auth.isAuthenticated && !auth.user) {
    await auth.fetchMe();
  }
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
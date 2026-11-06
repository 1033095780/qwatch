// stores/auth.ts — 登录态：token 存 localStorage（未勾选记住我时降级 sessionStorage）。
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { api, tokenStorage } from '@/api/client';
import type { AuthStatus, User } from '@/api/types';

export const useAuthStore = defineStore('auth', () => {
  const token = ref(tokenStorage.get());
  const user = ref<User | null>(null);
  const loading = ref(false);
  const error = ref('');
  const isAuthenticated = computed(() => !!token.value);
  const setupRequired = ref(false);
  const authStatus = ref<AuthStatus | null>(null);

  async function checkStatus(): Promise<AuthStatus> {
    const res = await api.authStatus();
    authStatus.value = res;
    setupRequired.value = res.setup_required;
    return res;
  }

  async function setup(password: string): Promise<void> {
    loading.value = true;
    error.value = '';
    try {
      const res = await api.setup(password);
      tokenStorage.set(res.token, true);
      token.value = res.token;
      user.value = res.user;
      setupRequired.value = false;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '初始化失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function login(password: string, remember = true): Promise<void> {
    loading.value = true;
    error.value = '';
    try {
      const res = await api.login(password);
      tokenStorage.set(res.token, remember);
      token.value = res.token;
      user.value = res.user;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '登录失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
    loading.value = true;
    error.value = '';
    try {
      const res = await api.changePassword(currentPassword, newPassword);
      tokenStorage.set(res.token, true);
      token.value = res.token;
      user.value = res.user;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '修改密码失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function fetchMe(): Promise<void> {
    if (!token.value) return;
    try {
      const res = await api.me();
      user.value = res.user;
    } catch {
      logout(false);
      // 让全局 401 处理器把当前页面直接送回登录页。
      window.dispatchEvent(new CustomEvent('qwatch:unauthorized'));
    }
  }

  async function logout(callApi = true): Promise<void> {
    if (callApi) {
      try {
        await api.logout();
      } catch {
        /* 登出接口失败不阻塞本地清理 */
      }
    }
    tokenStorage.clear();
    token.value = '';
    user.value = null;
  }

  return {
    token, user, loading, error, isAuthenticated, setupRequired, authStatus,
    checkStatus, setup, login, changePassword, fetchMe, logout,
  };
});
// stores/settings.ts — 显示偏好（涨跌配色/侧栏折叠）、全局刷新信号、设置页渠道数据（v0.2）。
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from '@/api/client';
import type { ChannelPatch, SettingsData, TestChannelResult, UpColorScheme } from '@/api/types';

const SCHEME_KEY = 'qwatch.updown';
const COLLAPSE_KEY = 'qwatch.collapsed';

function readScheme(): UpColorScheme {
  try {
    const v = localStorage.getItem(SCHEME_KEY);
    if (v === 'green_up' || v === 'red_up') return v;
  } catch {
    /* ignore */
  }
  return 'red_up';
}

export const useSettingsStore = defineStore('settings', () => {
  const upColorScheme = ref<UpColorScheme>(readScheme());
  const collapsed = ref(localStorage.getItem(COLLAPSE_KEY) === '1');
  const refreshSeq = ref(0);
  const lastRefreshAt = ref(Date.now());
  const data = ref<SettingsData | null>(null);
  const loading = ref(false);
  const error = ref('');

  const isGreenUp = computed(() => upColorScheme.value === 'green_up');

  function applyScheme(scheme: UpColorScheme): void {
    upColorScheme.value = scheme;
    document.documentElement.dataset.upScheme = scheme;
    try {
      localStorage.setItem(SCHEME_KEY, scheme);
    } catch {
      /* ignore */
    }
  }

  function toggleCollapse(): void {
    collapsed.value = !collapsed.value;
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed.value ? '1' : '0');
    } catch {
      /* ignore */
    }
  }

  /** 顶栏刷新：自增序号，页面 watch 后重新拉数据 */
  function triggerRefresh(): void {
    lastRefreshAt.value = Date.now();
    refreshSeq.value += 1;
  }

  async function load(force = false): Promise<void> {
    if (data.value && !force) return;
    loading.value = true;
    error.value = '';
    try {
      data.value = await api.settings();
    } catch (err) {
      error.value = err instanceof Error ? err.message : '设置加载失败';
    } finally {
      loading.value = false;
    }
  }

  /** 保存渠道配置（可只传要改的字段），返回掩码后的设置 */
  async function saveChannel(patch: ChannelPatch): Promise<SettingsData> {
    const res = await api.saveSettings({ channels: [patch] });
    data.value = res;
    return res;
  }

  async function setChannelEnabled(id: string, enabled: boolean): Promise<void> {
    await saveChannel({ id, enabled });
  }

  async function testChannel(id: string): Promise<TestChannelResult> {
    const res = await api.testChannel(id);
    await load(true);
    return res;
  }

  applyScheme(upColorScheme.value);

  return {
    upColorScheme, collapsed, refreshSeq, lastRefreshAt, data, loading, error, isGreenUp,
    applyScheme, toggleCollapse, triggerRefresh, load, saveChannel, setChannelEnabled, testChannel,
  };
});

<script setup lang="ts">
// App.vue — 全局 Provider：darkTheme + themeOverrides + 中文 locale + 消息/对话框/通知。
import {
  NConfigProvider, NDialogProvider, NLoadingBarProvider, NMessageProvider, NNotificationProvider,
  darkTheme, dateZhCN, zhCN,
} from 'naive-ui';
import { themeOverrides } from '@/styles/naive-theme';
</script>

<template>
  <n-config-provider
    :theme="darkTheme"
    :theme-overrides="themeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
    abstract
  >
    <n-loading-bar-provider>
      <n-message-provider :max="3">
        <n-dialog-provider>
          <n-notification-provider :max="3">
            <router-view />
          </n-notification-provider>
        </n-dialog-provider>
      </n-message-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>

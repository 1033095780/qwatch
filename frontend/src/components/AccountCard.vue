// AccountCard.vue — v0.4 账户卡片：券商、权益（无小数）、策略数/在线数、权益 sparkline；整卡进入该账户策略。
<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { Account } from '@/api/types';
import { fmtNumber } from '@/utils/format';
import NavSparkline from './NavSparkline.vue';

const props = defineProps<{ account: Account }>();
const router = useRouter();

const online = computed(() => props.account.online_strategies ?? 0);
const total = computed(() => props.account.strategy_count ?? 0);
const sparkline = computed(() => props.account.equity_sparkline ?? []);

function open(): void {
  void router.push({ path: '/strategies', query: { account_id: props.account.id } });
}
</script>

<template>
  <article class="account-card" role="link" tabindex="0" @click="open" @keydown.enter="open">
    <header class="head">
      <div class="identity">
        <span class="name truncate" :title="account.name">{{ account.name }}</span>
        <span v-if="account.broker && account.broker !== account.name" class="broker">{{ account.broker }}</span>
      </div>
    </header>
    <p v-if="account.description" class="desc truncate" :title="account.description">{{ account.description }}</p>

    <div class="equity-area">
      <div class="equity-copy">
        <span class="equity-label">账户权益</span>
        <strong class="equity-value mono">{{ account.equity !== null && account.equity !== undefined && account.equity !== '' ? '¥' + fmtNumber(account.equity, 0) : '—' }}</strong>
      </div>
      <div class="spark-wrap">
        <NavSparkline v-if="sparkline.length" :values="sparkline" :width="160" :height="42" />
      </div>
    </div>

    <footer class="foot">
      <span class="meta"><strong class="mono">{{ total }}</strong> 个策略 · <span class="mono">{{ online }}</span> 在线</span>
      <span class="link-hint">查看策略 →</span>
    </footer>
  </article>
</template>

<style scoped>
.account-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  padding: 16px 18px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, rgba(28, 37, 57, 0.68), rgba(16, 22, 35, 0.72));
  transition: border-color 160ms ease, transform 160ms ease;
  color: inherit;
}
.account-card:hover { border-color: var(--border-strong); transform: translateY(-1px); }
.account-card:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.identity { display: flex; align-items: center; gap: 8px; min-width: 0; }
.broker { flex: none; padding: 2px 7px; border: 1px solid var(--border); border-radius: 5px; color: var(--text-2); font-size: 10px; }
.name { font-size: 15px; font-weight: 600; color: #ffffff; }
.desc { margin-top: 6px; font-size: 11px; color: var(--text-3); }
.equity-area { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; margin-top: 16px; }
.equity-copy { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.equity-label { font-size: 10px; color: var(--text-3); }
.equity-value { font-size: 26px; line-height: 1.12; letter-spacing: -0.03em; color: #ffffff; white-space: nowrap; }
.spark-wrap { flex: 1 1 auto; max-width: 46%; min-width: 60px; opacity: 0.9; }
.foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 15px; padding-top: 10px; border-top: 1px solid var(--border); font-size: 10px; color: var(--text-3); }
.meta .mono { color: var(--text); font-size: 12px; }
.link-hint { color: var(--text-3); }
@media (max-width: 520px) {
  .equity-value { font-size: 22px; }
  .spark-wrap { max-width: 40%; }
}
</style>

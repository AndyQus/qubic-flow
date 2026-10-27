<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'

// Badge for archived wallets: neutral when empty, amber warning as soon as
// QUBIC (incl. Qearn locks) sits on the archived address again.
const props = defineProps({
  wallet:  { type: Object, required: true },
  compact: { type: Boolean, default: false },
})
const store = useAppStore()
const { t } = useTranslation()

const withFunds = computed(() => store.isArchivedWithFunds(props.wallet))

const tooltip = computed(() => {
  const w = props.wallet
  const lines = []
  if (withFunds.value) {
    const amount = store.hideAddresses ? '••••••' : store.walletHoldings(w).toLocaleString(store.locale)
    lines.push(t('archive.warn_tooltip', { amount }))
  }
  if (w.archived_reason) lines.push(t('archive.tooltip_reason', { reason: w.archived_reason }))
  if (w.archived_successor) {
    lines.push(t('archive.tooltip_successor', { successor: store.hideAddresses ? '••••••' : w.archived_successor }))
  }
  if (w.archived_at) {
    lines.push(`${t('archive.since')}: ${new Date(w.archived_at).toLocaleDateString(store.locale)}`)
  }
  return lines.join('\n')
})
</script>

<template>
  <span v-if="wallet.archived"
        :title="tooltip"
        :class="['pill text-xs py-0.5 px-2 inline-flex items-center gap-1 whitespace-nowrap cursor-help',
                 withFunds ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-gray-500/10 text-gray-400 border-gray-500/30']"
        @click.stop>
    <svg v-if="withFunds" xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
    </svg>
    <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/>
    </svg>
    <span v-if="!compact">{{ withFunds ? t('archive.warn_badge') : t('archive.badge') }}</span>
  </span>
</template>

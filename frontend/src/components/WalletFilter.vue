<script setup>
import { ref, computed } from 'vue'
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  wallets:    { type: Array, default: null },
})
const emit  = defineEmits(['update:modelValue'])
const store = useAppStore()
const { t } = useTranslation()
const open  = ref(false)
const selectedOwners = ref([])

const allWallets = computed(() => props.wallets ?? store.wallets)

const uniqueOwners = computed(() =>
  [...new Set(allWallets.value.map(w => w.owner).filter(Boolean))].sort()
)

const visibleWallets = computed(() =>
  selectedOwners.value.length
    ? allWallets.value.filter(w => selectedOwners.value.includes(w.owner))
    : allWallets.value
)

function toggle(id) {
  const next = props.modelValue.includes(id)
    ? props.modelValue.filter(x => x !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next)
}

function toggleOwner(owner) {
  if (selectedOwners.value.includes(owner)) {
    selectedOwners.value = selectedOwners.value.filter(o => o !== owner)
  } else {
    selectedOwners.value = [...selectedOwners.value, owner]
  }
  // Wallet-IDs aller aktiven Besitzer als neue Selektion emittieren
  if (selectedOwners.value.length === 0) {
    emit('update:modelValue', [])
  } else {
    const ids = allWallets.value
      .filter(w => selectedOwners.value.includes(w.owner))
      .map(w => w.id)
    emit('update:modelValue', ids)
  }
}

function clearAll() {
  selectedOwners.value = []
  emit('update:modelValue', [])
}

function walletLabel(w) {
  if (store.hideAddresses) return '••••••••••••'
  const name = w.label || (w.id.length > 10 ? `${w.id.slice(0, 5)}…${w.id.slice(-5)}` : w.id)
  return name.length > 15 ? name.slice(0, 15) + '…' : name
}

function walletTitle(w) {
  if (store.hideAddresses) return ''
  return w.label || w.id
}

function btnClass(id) {
  const selected = props.modelValue.includes(id)
  return [
    'btn-ghost text-sm py-2 w-44 transition-colors',
    selected
      ? 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal hover:bg-qubic-teal/30'
      : 'hover:bg-qubic-teal/10 hover:border-qubic-teal/60 hover:text-qubic-teal',
  ]
}

function ownerBtnClass(owner) {
  const selected = selectedOwners.value.includes(owner)
  return [
    'btn-ghost text-xs py-1 px-3 transition-colors',
    selected
      ? 'bg-violet-500/20 border-violet-400 text-violet-300 hover:bg-violet-500/30'
      : 'text-gray-400 hover:bg-violet-500/10 hover:border-violet-400/60 hover:text-violet-300',
  ]
}
</script>

<template>
  <div v-if="allWallets.length >= 1" class="card border-teal">
    <!-- Header -->
    <div class="flex items-center justify-between cursor-pointer select-none" @click="open = !open">
      <div class="flex items-center gap-1.5">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-qubic-teal/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z"/>
        </svg>
        <span class="text-sm text-gray-400 uppercase tracking-wide">{{ t('filter.wallet_filter') }}</span>
        <span v-if="modelValue.length" class="text-xs text-qubic-teal ml-1">({{ modelValue.length }})</span>
        <span v-if="selectedOwners.length" class="text-xs text-violet-400 ml-1">· {{ selectedOwners.length }} {{ t('filter.owner') }}</span>
      </div>
      <div class="flex items-center gap-3">
        <button v-if="modelValue.length || selectedOwners.length"
                class="btn-ghost text-xs py-0.5 px-3 text-red-400 border-red-400/40 hover:bg-red-400/10 hover:border-red-400 transition-colors"
                @click.stop="clearAll">
          {{ t('filter.clear_all') }}
        </button>
        <svg xmlns="http://www.w3.org/2000/svg"
             :class="['w-4 h-4 text-gray-500 transition-transform duration-200', open && 'rotate-180']"
             fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
        </svg>
      </div>
    </div>

    <div v-if="open" class="mt-3 space-y-3">
      <!-- Besitzer-Filter -->
      <div v-if="uniqueOwners.length" class="flex flex-wrap items-center gap-2 pb-3 border-b border-qubic-border/40">
        <span class="text-xs text-gray-500 uppercase tracking-wide">{{ t('filter.owner') }}:</span>
        <button
          v-for="owner in uniqueOwners"
          :key="owner"
          :class="ownerBtnClass(owner)"
          @click="toggleOwner(owner)"
        >
          {{ store.hideAddresses ? '••••••' : owner }}
        </button>
      </div>

      <!-- Wallet-Buttons -->
      <div class="flex flex-wrap gap-2">
        <button
          v-for="w in visibleWallets"
          :key="w.id"
          :class="btnClass(w.id)"
          :title="walletTitle(w)"
          @click="toggle(w.id)"
        >
          {{ walletLabel(w) }}
        </button>
      </div>
    </div>
  </div>
</template>

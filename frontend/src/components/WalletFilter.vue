<script setup>
import { useAppStore } from '../stores/app'

const props = defineProps({ modelValue: { type: Array, default: () => [] } })
const emit  = defineEmits(['update:modelValue'])
const store = useAppStore()

function toggle(id) {
  const next = props.modelValue.includes(id)
    ? props.modelValue.filter(x => x !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next)
}

function walletLabel(w) {
  if (store.hideAddresses) return '••••••••••••'
  return w.label || (w.id.length > 14 ? `${w.id.slice(0, 6)}…${w.id.slice(-6)}` : w.id)
}
</script>

<template>
  <div v-if="store.wallets.length > 1" class="border border-qubic-border rounded-xl px-3 py-2 space-y-2 bg-[#1a2d4a]">
    <div class="flex items-center justify-between">
      <span class="text-[10px] text-gray-400 uppercase tracking-wide">Wallet Filter</span>
      <button
        v-if="modelValue.length"
        class="text-xs text-gray-500 hover:text-gray-300"
        @click="emit('update:modelValue', [])"
      >
        × Alle
      </button>
    </div>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="w in store.wallets"
        :key="w.id"
        :class="['btn-ghost text-xs py-1', modelValue.includes(w.id) && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
        @click="toggle(w.id)"
      >
        {{ walletLabel(w) }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAppStore } from '../stores/app'

const props = defineProps({ modelValue: { type: Array, default: () => [] } })
const emit  = defineEmits(['update:modelValue'])
const store = useAppStore()
const open  = ref(false)

function toggle(id) {
  const next = props.modelValue.includes(id)
    ? props.modelValue.filter(x => x !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next)
}

function walletLabel(w) {
  if (store.hideAddresses) return '••••••••••••'
  const name = w.label || (w.id.length > 14 ? `${w.id.slice(0, 6)}…${w.id.slice(-6)}` : w.id)
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
</script>

<template>
  <div v-if="store.wallets.length > 1" class="card border-teal">
    <!-- Header (immer sichtbar) -->
    <div class="flex items-center justify-between cursor-pointer select-none" @click="open = !open">
      <div class="flex items-center gap-1.5">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-qubic-teal/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z"/>
        </svg>
        <span class="text-sm text-gray-400 uppercase tracking-wide">Wallet Filter</span>
        <span v-if="modelValue.length" class="text-xs text-qubic-teal ml-1">({{ modelValue.length }})</span>
      </div>
      <div class="flex items-center gap-3">
        <button v-if="modelValue.length"
                class="btn-ghost text-[10px] py-0.5 px-3 text-red-400 border-red-400/40 hover:bg-red-400/10 hover:border-red-400 transition-colors"
                @click.stop="emit('update:modelValue', [])">
          × Alle
        </button>
        <svg xmlns="http://www.w3.org/2000/svg"
             :class="['w-4 h-4 text-gray-500 transition-transform duration-200', open && 'rotate-180']"
             fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
        </svg>
      </div>
    </div>

    <!-- Buttons (ein-/ausklappbar) -->
    <div v-if="open" class="flex flex-wrap gap-2 mt-3">
      <button
        v-for="w in store.wallets"
        :key="w.id"
        :class="btnClass(w.id)"
        :title="walletTitle(w)"
        @click="toggle(w.id)"
      >
        {{ walletLabel(w) }}
      </button>
    </div>
  </div>
</template>

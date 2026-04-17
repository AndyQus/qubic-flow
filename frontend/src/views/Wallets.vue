<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'

const store = useAppStore()
const { t } = useTranslation()
const showForm = ref(false)
const form = ref({ id: '', label: '', note: '', wallet_type: 'PRIVATE' })

async function reload() { store.wallets = await api.wallets.list() }

async function submit() {
  await api.wallets.create(form.value)
  form.value = { id: '', label: '', note: '', wallet_type: 'PRIVATE' }
  showForm.value = false
  await reload()
}

async function remove(id) {
  if (!confirm('Delete wallet?')) return
  await api.wallets.remove(id)
  await reload()
}

onMounted(reload)
</script>

<template>
  <div class="flex items-center justify-between mb-4">
    <div class="flex gap-2">
      <button :class="['btn-ghost', store.walletFilter === 'all' && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'all'">{{ t('filter.all') }}</button>
      <button :class="['btn-ghost', store.walletFilter === 'private' && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'private'">{{ t('filter.private') }}</button>
      <button :class="['btn-ghost', store.walletFilter === 'business' && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'business'">{{ t('filter.business') }}</button>
    </div>
    <button class="btn" @click="showForm = !showForm">+ {{ t('wallet.add') }}</button>
  </div>

  <div v-if="showForm" class="card mb-4 space-y-3">
    <input v-model="form.id" :placeholder="t('wallet.address')" class="input w-full font-mono" />
    <input v-model="form.label" :placeholder="t('wallet.label')" class="input w-full" />
    <input v-model="form.note" :placeholder="t('wallet.note')" class="input w-full" />
    <select v-model="form.wallet_type" class="input w-full">
      <option value="PRIVATE">PRIVATE</option>
      <option value="BUSINESS">BUSINESS</option>
    </select>
    <button class="btn" @click="submit">{{ t('common.save') }}</button>
  </div>

  <div class="card overflow-hidden">
    <table class="w-full text-sm">
      <thead class="border-b border-qubic-border text-gray-400 text-xs uppercase">
        <tr>
          <th class="text-left p-3">{{ t('wallet.label') }}</th>
          <th class="text-left p-3">{{ t('wallet.address') }}</th>
          <th class="text-left p-3">{{ t('wallet.type') }}</th>
          <th class="text-left p-3">{{ t('wallet.note') }}</th>
          <th class="text-right p-3">{{ t('wallet.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!store.filteredWallets.length">
          <td colspan="5" class="text-center p-8 text-gray-500">{{ t('wallet.none') }}</td>
        </tr>
        <tr v-for="w in store.filteredWallets" :key="w.id" class="border-b border-qubic-border/50 hover:bg-qubic-bg/50">
          <td class="p-3 font-medium">
            <router-link :to="`/wallets/${w.id}`" class="hover:text-qubic-teal">{{ w.label }}</router-link>
          </td>
          <td class="p-3 font-mono text-xs text-gray-400">{{ w.id }}</td>
          <td class="p-3">
            <span :class="['pill', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
              {{ w.wallet_type }}
            </span>
          </td>
          <td class="p-3 text-gray-400">{{ w.note || '—' }}</td>
          <td class="p-3 text-right">
            <button @click="remove(w.id)" class="text-red-400 hover:text-red-300 text-sm">{{ t('wallet.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

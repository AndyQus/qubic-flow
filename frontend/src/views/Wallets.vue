<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'

const store = useAppStore()
const { t } = useTranslation()
const showForm  = ref(false)
const editingId = ref(null)
const error     = ref('')
const form      = ref({ id: '', label: '', note: '', wallet_type: 'PRIVATE' })
const editForm  = ref({ label: '', note: '', wallet_type: 'PRIVATE' })

async function reload() { store.wallets = await api.wallets.list() }

async function submit() {
  error.value = ''
  try {
    await api.wallets.create(form.value)
    form.value = { id: '', label: '', note: '', wallet_type: 'PRIVATE' }
    showForm.value = false
    await reload()
  } catch (e) {
    error.value = e.message.includes('409') ? 'Diese Adresse existiert bereits.' : `Fehler: ${e.message}`
  }
}

function startEdit(w) {
  editingId.value = w.id
  editForm.value = { label: w.label, note: w.note || '', wallet_type: w.wallet_type }
}

async function saveEdit(id) {
  await api.wallets.update(id, editForm.value)
  editingId.value = null
  await reload()
}

function cancelEdit() { editingId.value = null }

async function remove(id) {
  if (!confirm('Wallet löschen?')) return
  await api.wallets.remove(id)
  await reload()
}

function explorerUrl(addr) {
  return `https://explorer.qubic.org/network/address/${addr}`
}

function maskLabel(label, id) {
  if (!store.hideAddresses) return label
  const n = id.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % 101
  return `Wallet ${n}`
}

onMounted(reload)
</script>

<template>
  <!-- Toolbar -->
  <div class="flex items-center justify-between mb-4 gap-2 flex-wrap">
    <div class="flex gap-2">
      <button :class="['btn-ghost text-sm', store.walletFilter === 'all'      && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'all'">{{ t('filter.all') }}</button>
      <button :class="['btn-ghost text-sm', store.walletFilter === 'private'  && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'private'">{{ t('filter.private') }}</button>
      <button :class="['btn-ghost text-sm', store.walletFilter === 'business' && 'bg-qubic-teal/20 border-qubic-teal']"
              @click="store.walletFilter = 'business'">{{ t('filter.business') }}</button>
    </div>
    <button class="btn text-sm" @click="showForm = !showForm">+ {{ t('wallet.add') }}</button>
  </div>

  <!-- Add-Form -->
  <div v-if="showForm" class="card mb-4 space-y-3">
    <input v-model="form.id"    :placeholder="t('wallet.address')" class="input w-full font-mono text-xs" />
    <input v-model="form.label" :placeholder="t('wallet.label')"   class="input w-full text-xs" />
    <input v-model="form.note"  :placeholder="t('wallet.note')"    class="input w-full text-xs" />
    <select v-model="form.wallet_type" class="input w-full text-xs">
      <option value="PRIVATE">PRIVATE</option>
      <option value="BUSINESS">BUSINESS</option>
    </select>
    <p v-if="error" class="text-red-400 text-xs">{{ error }}</p>
    <button class="btn text-sm" @click="submit">{{ t('common.save') }}</button>
  </div>

  <!-- Mobile: card list -->
  <div class="sm:hidden space-y-2">
    <div v-if="!store.filteredWallets.length" class="card p-6 text-center text-gray-500 text-xs">
      {{ t('wallet.none') }}
    </div>
    <div v-for="w in store.filteredWallets" :key="w.id" class="card">
      <!-- Edit-Form (mobile) -->
      <div v-if="editingId === w.id" class="space-y-2 mb-2">
        <input v-model="editForm.label" :placeholder="t('wallet.label')" class="input w-full text-xs" />
        <input v-model="editForm.note"  :placeholder="t('wallet.note')"  class="input w-full text-xs" />
        <select v-model="editForm.wallet_type" class="input w-full text-xs">
          <option value="PRIVATE">PRIVATE</option>
          <option value="BUSINESS">BUSINESS</option>
        </select>
        <div class="flex gap-2">
          <button class="btn text-sm" @click="saveEdit(w.id)">{{ t('common.save') }}</button>
          <button class="btn-ghost text-sm" @click="cancelEdit">{{ t('common.cancel') }}</button>
        </div>
      </div>
      <div v-else class="flex items-center justify-between gap-2">
        <router-link :to="`/wallets/${w.id}`" class="flex items-center gap-2 min-w-0 flex-1 group">
          <div class="min-w-0">
            <div class="text-sm font-medium group-hover:text-qubic-teal transition-colors">{{ maskLabel(w.label, w.id) }}</div>
            <div class="text-[10px] font-mono text-gray-500 truncate">{{ store.hideAddresses ? '••••••••••••' : w.id }}</div>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-500 group-hover:text-qubic-teal flex-shrink-0 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </router-link>
        <div class="flex items-center gap-2 flex-shrink-0">
          <span :class="['pill text-[10px]', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
            {{ w.wallet_type }}
          </span>
          <a :href="explorerUrl(w.id)" target="_blank" rel="noopener" class="text-gray-500 hover:text-qubic-teal">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
          </a>
          <button @click="startEdit(w)" class="text-qubic-teal hover:text-qubic-cyan text-xs">{{ t('wallet.edit') }}</button>
          <button @click="remove(w.id)" class="text-red-400 hover:text-red-300 text-xs">{{ t('wallet.delete') }}</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Desktop: table -->
  <div class="card overflow-hidden hidden sm:block">
    <table class="w-full text-xs">
      <thead class="border-b border-qubic-border text-gray-400 uppercase">
        <tr>
          <th class="text-left p-3">{{ t('wallet.label') }}</th>
          <th class="text-left p-3">{{ t('wallet.address') }}</th>
          <th class="text-left p-3">{{ t('wallet.type') }}</th>
          <th class="text-left p-3 hidden md:table-cell">{{ t('wallet.note') }}</th>
          <th class="text-right p-3">{{ t('wallet.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!store.filteredWallets.length">
          <td colspan="5" class="text-center p-8 text-gray-500">{{ t('wallet.none') }}</td>
        </tr>
        <template v-for="w in store.filteredWallets" :key="w.id">
          <!-- Edit-Row -->
          <tr v-if="editingId === w.id" class="border-b border-qubic-border/50 bg-qubic-teal/5">
            <td class="p-2">
              <input v-model="editForm.label" :placeholder="t('wallet.label')" class="input w-full text-xs" />
            </td>
            <td class="p-2 font-mono text-gray-500 text-[10px]">
              {{ store.hideAddresses ? '••••••••••••' : w.id.slice(0,8) + '…' + w.id.slice(-8) }}
            </td>
            <td class="p-2">
              <select v-model="editForm.wallet_type" class="input text-xs">
                <option value="PRIVATE">PRIVATE</option>
                <option value="BUSINESS">BUSINESS</option>
              </select>
            </td>
            <td class="p-2 hidden md:table-cell">
              <input v-model="editForm.note" :placeholder="t('wallet.note')" class="input w-full text-xs" />
            </td>
            <td class="p-2 text-right">
              <div class="flex justify-end gap-2">
                <button class="btn text-sm py-1" @click="saveEdit(w.id)">{{ t('common.save') }}</button>
                <button class="btn-ghost text-sm py-1" @click="cancelEdit">{{ t('common.cancel') }}</button>
              </div>
            </td>
          </tr>
          <!-- Normal-Row -->
          <tr v-else class="border-b border-qubic-border/50 hover:bg-qubic-bg/50">
            <td class="p-3">
              <router-link :to="`/wallets/${w.id}`"
                           class="flex items-center gap-1.5 group font-medium hover:text-qubic-teal transition-colors">
                {{ maskLabel(w.label, w.id) }}
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-500 group-hover:text-qubic-teal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </router-link>
            </td>
            <td class="p-3">
              <div class="flex items-center gap-1.5">
                <span class="font-mono text-gray-400 text-[10px]" :title="store.hideAddresses ? '' : w.id">
                  {{ store.hideAddresses ? '••••••••••••' : w.id.slice(0, 8) + '…' + w.id.slice(-8) }}
                </span>
                <a :href="explorerUrl(w.id)" target="_blank" rel="noopener"
                   class="text-gray-600 hover:text-qubic-teal flex-shrink-0">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                </a>
              </div>
            </td>
            <td class="p-3">
              <span :class="['pill text-[10px]', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
                {{ w.wallet_type }}
              </span>
            </td>
            <td class="p-3 text-gray-400 hidden md:table-cell">{{ w.note || '—' }}</td>
            <td class="p-3 text-right">
              <div class="flex justify-end gap-3">
                <button @click="startEdit(w)" class="text-qubic-teal hover:text-qubic-cyan">{{ t('wallet.edit') }}</button>
                <button @click="remove(w.id)" class="text-red-400 hover:text-red-300">{{ t('wallet.delete') }}</button>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

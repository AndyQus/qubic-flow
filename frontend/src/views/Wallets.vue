<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import PageLoader from '../components/PageLoader.vue'
import { useQubicUtils } from '../composables/useQubicUtils'

const store = useAppStore()
const { t } = useTranslation()
const { explorerUrl, copyAddress, maskLabel } = useQubicUtils()
const showForm      = ref(false)
const loading       = ref(true)
const editingId     = ref(null)
const error         = ref('')
const editError     = ref('')
const selectedOwner = ref(null)
const form          = ref({ id: '', label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' })
const editForm      = ref({ label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' })

const uniqueOwners = computed(() =>
  [...new Set(store.wallets.map(w => w.owner).filter(Boolean))].sort()
)

const uniqueFunctions = computed(() =>
  [...new Set(store.wallets.map(w => w.function).filter(Boolean))].sort()
)

const displayedWallets = computed(() => {
  const base = Array.isArray(store.filteredWallets) ? store.filteredWallets : []
  if (!selectedOwner.value) return base
  return base.filter(w => w && w.owner === selectedOwner.value)
})

async function reload() {
  loading.value = true
  try { store.wallets = await api.wallets.list() }
  finally { loading.value = false }
}

async function submit() {
  error.value = ''
  try {
    await api.wallets.create(form.value)
    form.value = { id: '', label: '', owner: '', function: '', note: '', wallet_type: 'PRIVATE' }
    showForm.value = false
    await reload()
  } catch (e) {
    error.value = e.message.includes('409') ? t('wallet.address_exists') : `${t('node.url_error')}${e.message}`
  }
}

function startEdit(w) {
  editingId.value = w.id
  editForm.value = { label: w.label, owner: w.owner || '', function: w.function || '', note: w.note || '', wallet_type: w.wallet_type }
}

async function saveEdit(id) {
  editError.value = ''
  try {
    await api.wallets.update(id, editForm.value)
    editingId.value = null
    await reload()
  } catch (e) {
    editError.value = e.message
  }
}

function cancelEdit() { editingId.value = null }

async function remove(id) {
  if (!confirm(t('wallet.delete_confirm'))) return
  try {
    await api.wallets.remove(id)
    await reload()
  } catch (e) {
    error.value = e.message
  }
}


function fmtBalance(w) {
  if (w.balance == null) return t('wallet.balance_pending')
  if (store.hideAddresses) return '••••••'
  return w.balance.toLocaleString(store.locale)
}

function balanceSyncClass(w) {
  if (w.balance == null || w.balance_live == null) return 'text-gray-500'
  return w.balance === w.balance_live ? 'text-green-400' : 'text-yellow-400'
}

function balanceSyncTitle(w) {
  if (w.balance == null) return ''
  if (w.balance_live == null) return t('wallet.balance_no_live')
  return w.balance === w.balance_live ? t('wallet.balance_synced') : `${t('wallet.balance_drift')}: ${w.balance_live.toLocaleString(store.locale)}`
}

onMounted(reload)
</script>

<template>
  <!-- Toolbar -->
  <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
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

  <!-- Owner filter pills -->
  <div v-if="uniqueOwners.length" class="flex flex-wrap items-center gap-2 mb-4">
    <span class="text-xs text-gray-500 uppercase tracking-wide">{{ t('filter.owner') }}:</span>
    <button
      v-for="owner in uniqueOwners"
      :key="owner"
      :class="['btn-ghost text-xs py-1 px-3 transition-colors', selectedOwner === owner
        ? 'bg-violet-500/20 border-violet-400 text-violet-300 hover:bg-violet-500/30'
        : 'text-gray-400 hover:bg-violet-500/10 hover:border-violet-400/60 hover:text-violet-300']"
      @click="selectedOwner = selectedOwner === owner ? null : owner"
    >
      {{ store.hideAddresses ? '••••••' : owner }}
    </button>
  </div>

  <PageLoader v-if="loading" />

  <template v-else>
  <!-- Add-Form -->
  <div v-if="showForm" class="card mb-4 space-y-3">
    <input v-model="form.id"    :placeholder="t('wallet.address')" class="input w-full font-mono text-xs" />
    <input v-model="form.label" :placeholder="t('wallet.label')"   class="input w-full text-xs" />
    <input v-model="form.owner" :placeholder="t('wallet.owner')"   class="input w-full text-xs"
           list="owner-list-add" autocomplete="off" />
    <datalist id="owner-list-add">
      <option v-for="o in uniqueOwners" :key="o" :value="o" />
    </datalist>
    <input v-model="form.note"  :placeholder="t('wallet.note')"    class="input w-full text-xs" />
    <select v-model="form.wallet_type" class="input w-full text-xs">
      <option value="PRIVATE">PRIVATE</option>
      <option value="BUSINESS">BUSINESS</option>
    </select>
    <input v-model="form.function" :placeholder="t('wallet.function')" class="input w-full text-xs"
           list="function-list-add" autocomplete="off" />
    <datalist id="function-list-add">
      <option v-for="f in uniqueFunctions" :key="f" :value="f" />
    </datalist>
    <p v-if="error" class="text-red-400 text-xs">{{ error }}</p>
    <div class="flex gap-2">
      <button class="btn text-sm" @click="submit">{{ t('common.save') }}</button>
      <button class="btn-ghost text-sm" @click="showForm = false; error = ''">{{ t('common.cancel') }}</button>
    </div>
  </div>

  <!-- Mobile: card list -->
  <div class="sm:hidden space-y-2">
    <div v-if="!displayedWallets.length" class="card p-6 text-center text-gray-500 text-xs">
      {{ t('wallet.none') }}
    </div>
    <div v-for="w in displayedWallets" :key="w.id" class="card">
      <!-- Edit-Form (mobile) -->
      <div v-if="editingId === w.id" class="space-y-2 mb-2">
        <input v-model="editForm.label" :placeholder="t('wallet.label')" class="input w-full text-xs" />
        <input v-model="editForm.owner" :placeholder="t('wallet.owner')" class="input w-full text-xs"
               list="owner-list-edit" autocomplete="off" />
        <datalist id="owner-list-edit">
          <option v-for="o in uniqueOwners" :key="o" :value="o" />
        </datalist>
        <input v-model="editForm.note"  :placeholder="t('wallet.note')"  class="input w-full text-xs" />
        <select v-model="editForm.wallet_type" class="input w-full text-xs">
          <option value="PRIVATE">PRIVATE</option>
          <option value="BUSINESS">BUSINESS</option>
        </select>
        <input v-model="editForm.function" :placeholder="t('wallet.function')" class="input w-full text-xs"
               list="function-list-mobile-edit" autocomplete="off" />
        <datalist id="function-list-mobile-edit">
          <option v-for="f in uniqueFunctions" :key="f" :value="f" />
        </datalist>
        <p v-if="editError" class="text-red-400 text-xs">{{ editError }}</p>
        <div class="flex gap-2">
          <button class="btn text-sm" @click="saveEdit(w.id)">{{ t('common.save') }}</button>
          <button class="btn-ghost text-sm" @click="cancelEdit">{{ t('common.cancel') }}</button>
        </div>
      </div>
      <div v-else class="flex items-center justify-between gap-2">
        <router-link :to="`/wallets/${w.id}`" class="flex items-center gap-2 min-w-0 flex-1 group">
          <div class="min-w-0">
            <div class="text-sm font-medium group-hover:text-qubic-teal transition-colors">{{ maskLabel(w.label, w.id) }}</div>
            <div class="text-xs font-mono text-gray-500 truncate">{{ store.hideAddresses ? '••••••••••••' : w.id }}</div>
            <div class="flex items-center gap-1 mt-0.5">
              <span class="text-xs font-mono" :class="w.balance == null ? 'text-gray-600 italic' : 'text-gray-400'">{{ fmtBalance(w) }}</span>
              <span v-if="w.balance != null" :class="['text-xs', balanceSyncClass(w)]" :title="balanceSyncTitle(w)">●</span>
            </div>
          </div>
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-500 group-hover:text-qubic-teal flex-shrink-0 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </router-link>
        <div class="flex items-center gap-2 flex-shrink-0">
          <span :class="['pill text-xs', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
            {{ w.wallet_type }}
          </span>
          <button v-if="!store.hideAddresses" @click="copyAddress(w.id)"
                  class="icon-btn" :title="t('assets.copy')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
          <a :href="explorerUrl(w.id)" target="_blank" rel="noopener"
             class="icon-btn" :title="t('assets.explorer')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
          </a>
          <button @click="startEdit(w)" class="btn-action text-xs">{{ t('wallet.edit') }}</button>
          <button @click="remove(w.id)" class="btn-delete text-xs">{{ t('wallet.delete') }}</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Desktop: table -->
  <div class="card overflow-hidden hidden sm:block">
    <table class="table-std">
      <thead class="thead-std">
        <tr>
          <th class="th">{{ t('wallet.label') }}</th>
          <th class="th hidden md:table-cell">{{ t('wallet.owner') }}</th>
          <th class="th">{{ t('wallet.address') }}</th>
          <th class="th">{{ t('wallet.type') }}</th>
          <th class="th hidden md:table-cell">{{ t('wallet.function') }}</th>
          <th class="th hidden md:table-cell">{{ t('wallet.note') }}</th>
          <th class="th-right hidden lg:table-cell whitespace-nowrap">{{ t('wallet.balance') }} QUBIC</th>
          <th class="th-right hidden lg:table-cell whitespace-nowrap">{{ t('wallet.entries') }}</th>
          <th class="th-right">{{ t('wallet.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!displayedWallets.length">
          <td colspan="9" class="text-center p-8 text-gray-500">{{ t('wallet.none') }}</td>
        </tr>
        <template v-for="w in displayedWallets" :key="w.id">
          <!-- Edit-Row -->
          <tr v-if="editingId === w.id" class="tr-edit">
            <td class="p-2">
              <input v-model="editForm.label" :placeholder="t('wallet.label')" class="input w-full text-xs" />
            </td>
            <td class="p-2 hidden md:table-cell">
              <input v-model="editForm.owner" :placeholder="t('wallet.owner')" class="input w-full text-xs"
                     list="owner-list-desktop-edit" autocomplete="off" />
              <datalist id="owner-list-desktop-edit">
                <option v-for="o in uniqueOwners" :key="o" :value="o" />
              </datalist>
            </td>
            <td class="p-2 font-mono text-gray-500">
              {{ store.hideAddresses ? '••••••••••••' : w.id.slice(0, 5) + '…' + w.id.slice(-5) }}
            </td>
            <td class="p-2">
              <select v-model="editForm.wallet_type" class="input text-xs">
                <option value="PRIVATE">PRIVATE</option>
                <option value="BUSINESS">BUSINESS</option>
              </select>
            </td>
            <td class="p-2 hidden md:table-cell">
              <input v-model="editForm.function" :placeholder="t('wallet.function')" class="input w-full text-xs"
                     list="function-list-desktop-edit" autocomplete="off" />
              <datalist id="function-list-desktop-edit">
                <option v-for="f in uniqueFunctions" :key="f" :value="f" />
              </datalist>
            </td>
            <td class="p-2 hidden md:table-cell">
              <input v-model="editForm.note" :placeholder="t('wallet.note')" class="input w-full text-xs" />
            </td>
            <td class="p-2 hidden lg:table-cell"></td>
            <td class="p-2 hidden lg:table-cell"></td>
            <td class="p-2 hidden lg:table-cell"></td>
            <td class="p-2 text-right">
              <p v-if="editError" class="text-red-400 text-xs text-right mb-1">{{ editError }}</p>
              <div class="flex justify-end gap-2">
                <button class="btn text-sm py-1" @click="saveEdit(w.id)">{{ t('common.save') }}</button>
                <button class="btn-ghost text-sm py-1" @click="cancelEdit">{{ t('common.cancel') }}</button>
              </div>
            </td>
          </tr>
          <!-- Normal-Row -->
          <tr v-else class="tr-row">
            <td class="td">
              <router-link :to="`/wallets/${w.id}`"
                           class="flex items-center gap-1.5 group font-medium hover:text-qubic-teal transition-colors">
                {{ maskLabel(w.label, w.id) }}
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 text-gray-500 group-hover:text-qubic-teal transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              </router-link>
            </td>
            <td class="td text-gray-400 hidden md:table-cell">{{ store.hideAddresses ? '••••••' : (w.owner || '—') }}</td>
            <td class="td">
              <div class="flex items-center gap-2 font-mono text-gray-400">
                <span :title="store.hideAddresses ? '' : w.id">
                  {{ store.hideAddresses ? '••••••••••••' : w.id.slice(0, 5) + '…' + w.id.slice(-5) }}
                </span>
                <button v-if="!store.hideAddresses" @click="copyAddress(w.id)"
                        class="icon-btn" :title="t('assets.copy')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
                <a :href="explorerUrl(w.id)" target="_blank" rel="noopener"
                   class="icon-btn" :title="t('assets.explorer')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                </a>
              </div>
            </td>
            <td class="td">
              <span :class="['pill', w.wallet_type === 'BUSINESS' && 'bg-orange-500/20 text-orange-400 border-orange-500/30']">
                {{ w.wallet_type }}
              </span>
            </td>
            <td class="td text-gray-400 hidden md:table-cell">{{ w.function || '—' }}</td>
            <td class="td text-gray-400 hidden md:table-cell">{{ w.note || '—' }}</td>
            <td class="td hidden lg:table-cell text-right">
              <div class="flex items-center justify-end gap-1.5">
                <span class="font-mono whitespace-nowrap" :class="w.balance == null ? 'text-gray-500 italic' : 'text-gray-300'">
                  {{ fmtBalance(w) }}
                </span>
                <span v-if="w.balance != null" :class="['text-xs', balanceSyncClass(w)]" :title="balanceSyncTitle(w)">●</span>
              </div>
            </td>
            <td class="td hidden lg:table-cell text-right font-mono text-gray-400">
              {{ w.total_events != null ? w.total_events.toLocaleString(store.locale) : '—' }}
            </td>
            <td class="td text-right">
              <div class="flex justify-end gap-3">
                <button @click="startEdit(w)" class="btn-action">{{ t('wallet.edit') }}</button>
                <button @click="remove(w.id)" class="btn-delete">{{ t('wallet.delete') }}</button>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
  </template>
</template>

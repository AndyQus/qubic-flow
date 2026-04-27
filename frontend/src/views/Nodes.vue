<script setup>
import { ref, watch, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import PageLoader from '../components/PageLoader.vue'
import PageHeader from '../components/PageHeader.vue'

const store = useAppStore()
const { t } = useTranslation()
const showForm = ref(false)
const loading  = ref(true)
const error    = ref('')
const editId   = ref(null)
const DEFAULT_RPC = 'https://rpc.qubic.org'
const DEFAULT_BOB = 'https://bobnet.qubic.li'
const isDev = import.meta.env.DEV
const form = ref({ url: DEFAULT_RPC, node_type: 'RPC', label: '', priority: 1 })

watch(() => form.value.node_type, (type) => {
  if (!editId.value) {
    form.value.url = type === 'BOB_NODE' ? DEFAULT_BOB : DEFAULT_RPC
  }
})

async function reload() {
  loading.value = true
  try { store.nodes = await api.nodes.list() }
  finally { loading.value = false }
}

function startEdit(n) {
  editId.value  = n.id
  form.value    = { url: n.url, node_type: n.node_type, label: n.label, priority: n.priority }
  showForm.value = true
}

function cancelForm() {
  editId.value   = null
  showForm.value = false
  error.value    = ''
  form.value     = { url: DEFAULT_RPC, node_type: 'RPC', label: '', priority: 1 }
}

async function submit() {
  error.value = ''
  try {
    if (editId.value) {
      await api.nodes.update(editId.value, form.value)
    } else {
      await api.nodes.create(form.value)
    }
    cancelForm()
    await reload()
  } catch (e) {
    error.value = e.message.includes('409') ? t('node.url_exists') : `${t('node.url_error')}${e.message}`
  }
}

async function toggle(id) {
  const node = store.nodes.find(n => n.id === id)
  if (!node) return
  const prev = node.is_active
  node.is_active = prev ? 0 : 1
  try {
    await api.nodes.toggle(id)
    await reload()
  } catch (e) {
    node.is_active = prev
    error.value = e.message
  }
}

async function remove(id) {
  if (!confirm(t('node.delete_confirm'))) return
  await api.nodes.remove(id)
  await reload()
}

function healthColor(status) {
  if (status === 'ONLINE')   return 'text-green-400'
  if (status === 'DEGRADED') return 'text-yellow-400'
  return 'text-red-400'
}

onMounted(reload)
</script>

<template>
  <div class="space-y-3">
  <PageHeader :title="t('nav.nodes')" :hint="t('page_hint.nodes')">
    <button class="btn" @click="editId = null; showForm = !showForm">+ {{ t('node.add') }}</button>
  </PageHeader>

  <PageLoader v-if="loading" />

  <template v-else>
  <div v-if="showForm" class="card mb-4 space-y-3">
    <h3 class="text-sm font-bold uppercase text-gray-400">{{ editId ? t('node.edit') : t('node.add') }}</h3>
    <div>
      <input v-model="form.url" :placeholder="t('node.url')" class="input w-full" />
      <p v-if="form.node_type === 'BOB_NODE'" class="text-xs text-amber-400 mt-1">⚠ {{ t('node.bob_hint') }}: <span class="font-mono">http://your-bob-node:40420</span></p>
      <p v-else class="text-xs text-gray-400 mt-1">{{ t('node.url_default') }}: <span class="font-mono">https://rpc.qubic.org</span></p>
    </div>
    <select v-model="form.node_type" class="input w-full">
      <option value="RPC">RPC</option>
      <option v-if="isDev" value="BOB_NODE">BOB_NODE</option>
    </select>
    <input v-model="form.label" :placeholder="t('node.label')" class="input w-full" />
    <input v-model.number="form.priority" type="number" min="1" max="5" class="input w-full" />
    <p v-if="error" class="text-red-400 text-xs">{{ error }}</p>
    <div class="flex gap-2">
      <button class="btn" @click="submit">{{ t('common.save') }}</button>
      <button class="btn-ghost text-sm" @click="cancelForm">{{ t('common.cancel') }}</button>
    </div>
  </div>

  <!-- Mobile: cards -->
  <div class="sm:hidden space-y-2">
    <div v-for="n in store.nodes" :key="n.id"
         :class="['card space-y-2', !n.is_active && 'opacity-40']">
      <div class="flex items-start justify-between gap-2">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span v-if="n.is_sync_active" class="relative flex h-2.5 w-2.5 shrink-0" :title="t('node.sync_active_hint')">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-qubic-teal opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-qubic-teal"></span>
            </span>
            <span class="font-mono text-xs text-gray-300 break-all">{{ n.url }}</span>
          </div>
          <div class="flex items-center gap-2 mt-1 flex-wrap">
            <span class="pill">{{ n.node_type }}</span>
            <span v-if="n.label" class="text-xs text-gray-400">{{ n.label }}</span>
            <span class="text-xs text-gray-500">{{ t('node.priority') }}: {{ n.priority }}</span>
          </div>
        </div>
        <button @click="toggle(n.id)"
                :class="['relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200 focus:outline-none',
                         n.is_active ? 'bg-qubic-teal' : 'bg-gray-600']">
          <span :class="['inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200',
                         n.is_active ? 'translate-x-4' : 'translate-x-1']" />
        </button>
      </div>
      <div class="flex items-center gap-4 text-xs flex-wrap">
        <span :class="healthColor(n.health_status)">● {{ n.health_status }}</span>
        <span class="text-gray-400">{{ t('node.tick') }}: <span class="font-mono">{{ n.tick || '—' }}</span></span>
        <span class="text-gray-400">{{ n.response_time_ms ? `${n.response_time_ms} ms` : '—' }}</span>
        <span v-if="n.fail_count" class="text-gray-500">({{ n.fail_count }}×)</span>
      </div>
      <div v-if="n.last_error" class="text-xs text-red-400/70 break-all">{{ n.last_error }}</div>
      <div class="flex gap-2 pt-1">
        <button @click="startEdit(n)" class="btn-action text-xs">{{ t('wallet.edit') }}</button>
        <button @click="remove(n.id)" class="btn-delete text-xs">{{ t('wallet.delete') }}</button>
      </div>
    </div>
  </div>

  <!-- Desktop: table -->
  <div class="card overflow-hidden hidden sm:block">
    <div class="overflow-x-auto">
      <table class="table-std">
        <thead class="thead-std">
          <tr>
            <th class="th">{{ t('node.priority') }}</th>
            <th class="th w-8"></th>
            <th class="th">{{ t('node.url') }}</th>
            <th class="th">{{ t('node.type') }}</th>
            <th class="th">{{ t('node.label') }}</th>
            <th class="th">{{ t('node.tick') }}</th>
            <th class="th">{{ t('node.response') }}</th>
            <th class="th">{{ t('node.health') }}</th>
            <th class="th-center">{{ t('node.active') }}</th>
            <th class="th-right">{{ t('wallet.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in store.nodes" :key="n.id" :class="['border-b border-qubic-border/50 transition-opacity', !n.is_active && 'opacity-40']">
            <td class="td">{{ n.priority }}</td>
            <td class="td text-center">
              <span v-if="n.is_sync_active"
                    class="relative flex h-2.5 w-2.5 mx-auto"
                    :title="t('node.sync_active_hint')">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-qubic-teal opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-qubic-teal"></span>
              </span>
            </td>
            <td class="td font-mono">{{ n.url }}</td>
            <td class="td"><span class="pill">{{ n.node_type }}</span></td>
            <td class="td text-gray-300">{{ n.label || '—' }}</td>
            <td class="td font-mono">{{ n.tick || '—' }}</td>
            <td class="td">{{ n.response_time_ms ? `${n.response_time_ms} ms` : '—' }}</td>
            <td class="td">
              <span :class="healthColor(n.health_status)" :title="n.last_checked ? 'Zuletzt geprüft: ' + n.last_checked : ''">● {{ n.health_status }}</span>
              <span v-if="n.fail_count" class="ml-1.5 text-xs text-gray-500">({{ n.fail_count }}×)</span>
              <div v-if="n.last_error" class="text-xs text-red-400/70 mt-0.5 max-w-xs truncate" :title="n.last_error">
                {{ n.last_error }}
              </div>
            </td>
            <td class="td text-center">
              <button @click="toggle(n.id)"
                      :class="['relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 focus:outline-none',
                               n.is_active ? 'bg-qubic-teal' : 'bg-gray-600']">
                <span :class="['inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200',
                               n.is_active ? 'translate-x-4' : 'translate-x-1']" />
              </button>
            </td>
            <td class="td text-right flex justify-end gap-3">
              <button @click="startEdit(n)" class="btn-action">{{ t('wallet.edit') }}</button>
              <button @click="remove(n.id)" class="btn-delete">{{ t('wallet.delete') }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  </template>
  </div>
</template>

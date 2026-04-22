<script setup>
import { ref, watch, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import PageLoader from '../components/PageLoader.vue'

const store = useAppStore()
const { t } = useTranslation()
const showForm = ref(false)
const loading  = ref(true)
const error    = ref('')
const editId   = ref(null)
const DEFAULT_RPC = 'https://rpc.qubic.org'
const DEFAULT_BOB = 'https://bobnet.qubic.li/'
const form = ref({ url: DEFAULT_BOB, node_type: 'BOB_NODE', label: '', priority: 1 })

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
  form.value     = { url: DEFAULT_BOB, node_type: 'BOB_NODE', label: '', priority: 1 }
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
  if (node) node.is_active = node.is_active ? 0 : 1
  await api.nodes.toggle(id)
  await reload()
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
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-xl font-bold">Nodes</h2>
    <button class="btn" @click="editId = null; showForm = !showForm">+ {{ t('node.add') }}</button>
  </div>

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
      <option value="BOB_NODE">BOB_NODE</option>
    </select>
    <input v-model="form.label" :placeholder="t('node.label')" class="input w-full" />
    <input v-model.number="form.priority" type="number" min="1" max="5" class="input w-full" />
    <p v-if="error" class="text-red-400 text-xs">{{ error }}</p>
    <div class="flex gap-2">
      <button class="btn" @click="submit">{{ t('common.save') }}</button>
      <button class="btn-ghost text-sm" @click="cancelForm">{{ t('common.cancel') }}</button>
    </div>
  </div>

  <div class="card overflow-hidden">
    <table class="w-full text-xs">
      <thead class="border-b border-qubic-border text-gray-400 uppercase">
        <tr>
          <th class="text-left p-3">{{ t('node.priority') }}</th>
          <th class="text-left p-3">{{ t('node.url') }}</th>
          <th class="text-left p-3">{{ t('node.type') }}</th>
          <th class="text-left p-3">{{ t('node.label') }}</th>
          <th class="text-left p-3">{{ t('node.tick') }}</th>
          <th class="text-left p-3">{{ t('node.response') }}</th>
          <th class="text-left p-3">{{ t('node.health') }}</th>
          <th class="text-center p-3">{{ t('node.active') }}</th>
          <th class="text-right p-3">{{ t('wallet.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="n in store.nodes" :key="n.id" :class="['border-b border-qubic-border/50 transition-opacity', !n.is_active && 'opacity-40']">
          <td class="p-3">{{ n.priority }}</td>
          <td class="p-3 font-mono text-xs">{{ n.url }}</td>
          <td class="p-3"><span class="pill text-xs">{{ n.node_type }}</span></td>
          <td class="p-3 text-gray-300">{{ n.label || '—' }}</td>
          <td class="p-3 font-mono">{{ n.tick || '—' }}</td>
          <td class="p-3">{{ n.response_time_ms ? `${n.response_time_ms} ms` : '—' }}</td>
          <td class="p-3"><span :class="healthColor(n.health_status)">● {{ n.health_status }}</span></td>
          <td class="p-3 text-center">
            <button @click="toggle(n.id)"
                    :class="['relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 focus:outline-none',
                             n.is_active ? 'bg-qubic-teal' : 'bg-gray-600']">
              <span :class="['inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform duration-200',
                             n.is_active ? 'translate-x-4' : 'translate-x-1']" />
            </button>
          </td>
          <td class="p-3 text-right flex justify-end gap-3">
            <button @click="startEdit(n)" class="text-qubic-teal hover:text-qubic-cyan">{{ t('wallet.edit') }}</button>
            <button @click="remove(n.id)" class="text-red-400 hover:text-red-300">{{ t('wallet.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  </template>
</template>

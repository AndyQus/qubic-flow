<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'

const store = useAppStore()
const { t } = useTranslation()
const showForm = ref(false)
const error = ref('')
const DEFAULT_RPC = 'https://rpc.qubic.org'
const form = ref({ url: DEFAULT_RPC, node_type: 'RPC', label: 'Qubic RPC', priority: 1 })

async function reload() { store.nodes = await api.nodes.list() }

async function submit() {
  error.value = ''
  try {
    await api.nodes.create(form.value)
    form.value = { url: DEFAULT_RPC, node_type: 'RPC', label: 'Qubic RPC', priority: 1 }
    showForm.value = false
    await reload()
  } catch (e) {
    error.value = e.message.includes('409') ? 'Diese URL existiert bereits.' : `Fehler: ${e.message}`
  }
}

async function remove(id) {
  if (!confirm('Delete node?')) return
  await api.nodes.remove(id)
  await reload()
}

function healthColor(status) {
  if (status === 'ONLINE') return 'text-green-400'
  if (status === 'DEGRADED') return 'text-yellow-400'
  return 'text-red-400'
}

onMounted(reload)
</script>

<template>
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-xl font-bold">Nodes</h2>
    <button class="btn" @click="showForm = !showForm">+ {{ t('node.add') }}</button>
  </div>

  <div v-if="showForm" class="card mb-4 space-y-3">
    <div>
      <input v-model="form.url" :placeholder="t('node.url')" class="input w-full" />
      <p class="text-xs text-gray-400 mt-1">Standard: <span class="font-mono">https://rpc.qubic.org</span></p>
    </div>
    <select v-model="form.node_type" class="input w-full">
      <option value="RPC">RPC</option>
      <option value="BOB_NODE">BOB_NODE</option>
      <option value="LITE_NODE">LITE_NODE</option>
    </select>
    <input v-model="form.label" :placeholder="t('node.label')" class="input w-full" />
    <input v-model.number="form.priority" type="number" min="1" max="5" class="input w-full" />
    <p v-if="error" class="text-red-400 text-xs">{{ error }}</p>
    <button class="btn" @click="submit">{{ t('common.save') }}</button>
  </div>

  <div class="card overflow-hidden">
    <table class="w-full text-sm">
      <thead class="border-b border-qubic-border text-gray-400 text-xs uppercase">
        <tr>
          <th class="text-left p-3">{{ t('node.priority') }}</th>
          <th class="text-left p-3">{{ t('node.url') }}</th>
          <th class="text-left p-3">{{ t('node.type') }}</th>
          <th class="text-left p-3">{{ t('node.tick') }}</th>
          <th class="text-left p-3">{{ t('node.response') }}</th>
          <th class="text-left p-3">{{ t('node.health') }}</th>
          <th class="text-right p-3">{{ t('wallet.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="n in store.nodes" :key="n.id" class="border-b border-qubic-border/50">
          <td class="p-3">{{ n.priority }}</td>
          <td class="p-3 font-mono text-xs">{{ n.url }}</td>
          <td class="p-3"><span class="pill">{{ n.node_type }}</span></td>
          <td class="p-3 font-mono">{{ n.tick || '—' }}</td>
          <td class="p-3">{{ n.response_time_ms ? `${n.response_time_ms} ms` : '—' }}</td>
          <td class="p-3"><span :class="healthColor(n.health_status)">● {{ n.health_status }}</span></td>
          <td class="p-3 text-right">
            <button @click="remove(n.id)" class="text-red-400 hover:text-red-300 text-sm">{{ t('wallet.delete') }}</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

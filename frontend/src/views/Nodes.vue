<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'
import PageLoader from '../components/PageLoader.vue'
import PageHeader from '../components/PageHeader.vue'

const store = useAppStore()
const { t } = useTranslation()
const route = useRoute()
const router = useRouter()

const activeTab = ref(route.query.tab === 'logs' ? 'logs' : 'nodes')
const showForm = ref(false)
const loading  = ref(true)
const error    = ref('')
const editId   = ref(null)
const DEFAULT_RPC = 'https://rpc.qubic.org'
const DEFAULT_BOB = 'https://bobnet.qubic.li'
const isDev = import.meta.env.DEV
const form = ref({ url: DEFAULT_RPC, node_type: 'RPC', label: '', priority: 1 })

const logs = ref([])
const logsLoading = ref(false)
const checkingNodeId = ref(null)
const logLevelFilter = ref('ALL')
const logsPage = ref(1)
const LOGS_PER_PAGE = 50

const LOG_LEVELS = ['ALL', 'ERROR', 'WARNING', 'INFO']

const filteredLogs = computed(() => {
  if (logLevelFilter.value === 'ALL') return logs.value
  return logs.value.filter(e => e.level === logLevelFilter.value)
})

const logsTotalPages = computed(() => Math.max(1, Math.ceil(filteredLogs.value.length / LOGS_PER_PAGE)))

const pagedLogs = computed(() => {
  const start = (logsPage.value - 1) * LOGS_PER_PAGE
  return filteredLogs.value.slice(start, start + LOGS_PER_PAGE)
})

watch(logLevelFilter, () => { logsPage.value = 1 })

watch(() => route.query, (q) => {
  activeTab.value = q.tab === 'logs' ? 'logs' : 'nodes'
})

watch(activeTab, (tab) => {
  if (tab === 'logs') loadLogs()
})

function setActiveTab(tab) {
  router.push({ path: '/nodes', query: tab === 'nodes' ? {} : { tab } })
}

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

async function loadLogs() {
  logsLoading.value = true
  try {
    logs.value = await api.nodes.logs()
    store.setNodeLogError(logs.value.slice(0, 50).some(e => e.level === 'ERROR'))
  } finally {
    logsLoading.value = false
  }
}

async function triggerCheckNow(id) {
  checkingNodeId.value = id
  try {
    await api.nodes.checkNow(id)
    await new Promise(r => setTimeout(r, 2000))
    await reload()
    if (activeTab.value === 'logs') await loadLogs()
  } finally {
    checkingNodeId.value = null
  }
}

function logLevelClass(level) {
  if (level === 'ERROR')   return 'text-red-400'
  if (level === 'WARNING') return 'text-yellow-400'
  if (level === 'INFO')    return 'text-green-400/80'
  return 'text-gray-400'
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
    <div class="flex items-center gap-2">
      <button :class="['tab-btn', activeTab === 'nodes' && 'tab-btn-active']"
              @click="setActiveTab('nodes')">{{ t('node.tab_nodes') }}</button>
      <button :class="['tab-btn relative', activeTab === 'logs' && 'tab-btn-active']"
              @click="setActiveTab('logs')">
        {{ t('node.tab_logs') }}
        <span v-if="store.nodeLogError"
              class="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-red-500"
              :title="t('node.logs_error_badge')" />
      </button>
    </div>
  </PageHeader>

  <PageLoader v-if="loading && activeTab === 'nodes'" />

  <!-- NODES TAB -->
  <template v-if="activeTab === 'nodes' && !loading">
    <div class="flex justify-end">
      <button class="btn" @click="editId = null; showForm = !showForm">+ {{ t('node.add') }}</button>
    </div>

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
          <button @click="triggerCheckNow(n.id)" :disabled="checkingNodeId === n.id" class="btn-action" :title="t('node.check_now_hint')">
            <svg xmlns="http://www.w3.org/2000/svg" :class="['w-3.5 h-3.5', checkingNodeId === n.id && 'animate-spin']" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
          </button>
          <button @click="startEdit(n)" class="btn-action" :title="t('wallet.edit')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button @click="remove(n.id)" class="btn-delete" :title="t('wallet.delete')">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
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
                <button @click="triggerCheckNow(n.id)" :disabled="checkingNodeId === n.id" class="btn-action" :title="t('node.check_now_hint')">
                  <svg xmlns="http://www.w3.org/2000/svg" :class="['w-3.5 h-3.5', checkingNodeId === n.id && 'animate-spin']" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
                </button>
                <button @click="startEdit(n)" class="btn-action" :title="t('wallet.edit')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button @click="remove(n.id)" class="btn-delete" :title="t('wallet.delete')">
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </template>

  <!-- LOGS TAB -->
  <template v-if="activeTab === 'logs'">
    <!-- Filter row -->
    <div class="flex flex-wrap items-center gap-2">
      <button v-for="lvl in LOG_LEVELS" :key="lvl"
              @click="logLevelFilter = lvl"
              :class="['tab-btn text-xs', logLevelFilter === lvl ? 'tab-btn-active' : '']">
        <span v-if="lvl !== 'ALL'" :class="logLevelClass(lvl)">●</span>
        {{ lvl === 'ALL' ? t('node.logs_all') : lvl }}
      </button>
      <div class="ml-auto flex items-center gap-3">
        <span class="text-xs text-gray-500">{{ filteredLogs.length }} {{ t('node.logs_count') }}</span>
        <button @click="loadLogs" class="btn">&#x27F3; Refresh</button>
      </div>
    </div>

    <PageLoader v-if="logsLoading" />
    <template v-else>
      <div v-if="filteredLogs.length === 0" class="card text-center text-gray-500 text-sm py-8">
        {{ t('node.logs_empty') }}
      </div>
      <template v-else>
        <!-- Desktop table -->
        <div class="card overflow-hidden hidden sm:block">
          <div class="overflow-x-auto">
            <table class="table-std">
              <thead class="thead-std">
                <tr>
                  <th class="th w-40">{{ t('node.logs_time') }}</th>
                  <th class="th w-20">{{ t('node.logs_level') }}</th>
                  <th class="th w-24">{{ t('node.logs_source') }}</th>
                  <th class="th">{{ t('node.logs_message') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(entry, i) in pagedLogs" :key="i" class="border-b border-qubic-border/30">
                  <td class="td font-mono text-gray-500 whitespace-nowrap">{{ entry.ts }}</td>
                  <td class="td"><span :class="['text-xs font-mono font-semibold', logLevelClass(entry.level)]">{{ entry.level }}</span></td>
                  <td class="td"><span class="pill text-xs">{{ entry.source }}</span></td>
                  <td class="td text-xs text-gray-300 break-all">{{ entry.message }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Mobile cards -->
        <div class="sm:hidden space-y-2">
          <div v-for="(entry, i) in pagedLogs" :key="i" class="card space-y-1 py-2">
            <div class="flex items-center gap-2">
              <span :class="['text-xs font-mono font-semibold', logLevelClass(entry.level)]">{{ entry.level }}</span>
              <span class="pill text-xs">{{ entry.source }}</span>
              <span class="text-xs text-gray-500 ml-auto font-mono">{{ entry.ts }}</span>
            </div>
            <p class="text-xs text-gray-300 break-all">{{ entry.message }}</p>
          </div>
        </div>

        <!-- Paging -->
        <div v-if="logsTotalPages > 1" class="flex justify-end">
          <div class="flex items-center gap-1">
            <button @click="logsPage = 1" :disabled="logsPage === 1" class="btn-ghost text-xs px-2 py-1 disabled:opacity-30">«</button>
            <button @click="logsPage--" :disabled="logsPage === 1" class="btn-ghost text-xs px-2 py-1 disabled:opacity-30">‹</button>
            <span class="text-xs text-gray-400 px-2">{{ logsPage }} / {{ logsTotalPages }}</span>
            <button @click="logsPage++" :disabled="logsPage === logsTotalPages" class="btn-ghost text-xs px-2 py-1 disabled:opacity-30">›</button>
            <button @click="logsPage = logsTotalPages" :disabled="logsPage === logsTotalPages" class="btn-ghost text-xs px-2 py-1 disabled:opacity-30">»</button>
          </div>
        </div>
      </template>
    </template>
  </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useTranslation } from 'i18next-vue'
import { api } from '../api'
import { useAppStore } from '../stores/app'
import { useQubicUtils } from '../composables/useQubicUtils'

const { t } = useTranslation()
const store = useAppStore()
const { shortAddr, copyValue } = useQubicUtils()

const positions = ref([])
const loadingPositions = ref(false)
const error = ref(null)

// check / apply job
const job = ref(null)
const preview = ref(null)          // result of the dry run
const applied = ref(null)          // result of the real run
const selected = ref(new Set())    // confirmed reconstruction keys
let pollTimer = null

// interest override
const editingKey = ref(null)
const editValue = ref('')
const savingInterest = ref(false)

const running = computed(() => job.value?.state === 'running')

function walletName(id) {
  if (store.hideAddresses) return '••••••••••••'
  const w = store.wallets.find(x => x.id === id)
  if (!w) return shortAddr(id)
  return w.owner ? `${w.label} - ${w.owner}` : w.label
}

function fmtQu(n) {
  return n == null ? '—' : Number(n).toLocaleString(store.locale)
}

function fmtRate(interest, principal) {
  if (interest == null || !principal) return '—'
  return (interest / principal * 100).toLocaleString(store.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' %'
}

function fmtDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString(store.locale) } catch { return iso }
}

const STATUS_CLASS = {
  LOCKED: 'bg-sky-500/20 text-sky-300',
  PAID: 'bg-green-500/20 text-green-300',
  EARLY_UNLOCKED: 'bg-violet-500/20 text-violet-300',
  MISSING: 'bg-red-500/20 text-red-300',
  RECONSTRUCTED: 'bg-amber-500/20 text-amber-300',
}

async function loadPositions() {
  loadingPositions.value = true
  try {
    positions.value = await api.qearn.positions()
  } catch (e) {
    error.value = e.message
  } finally {
    loadingPositions.value = false
  }
}

const positionsByWallet = computed(() => {
  const map = new Map()
  for (const p of positions.value) {
    if (!map.has(p.wallet_id)) map.set(p.wallet_id, [])
    map.get(p.wallet_id).push(p)
  }
  return [...map.entries()]
})

const totals = computed(() => {
  let locked = 0, interest = 0
  for (const p of positions.value) {
    if (p.status === 'LOCKED') locked += (p.principal - p.early_unlocked)
    if (p.interest != null && ['PAID', 'RECONSTRUCTED'].includes(p.status)) interest += p.interest
    for (const e of p.detail?.early || []) {
      if (['PAID', 'RECONSTRUCTED'].includes(e.status) && e.interest != null) interest += e.interest
    }
  }
  return { locked, interest }
})

function stopPolling() {
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
}

async function poll(onDone) {
  try {
    job.value = await api.qearn.job()
  } catch (e) {
    error.value = e.message
    return
  }
  if (job.value.state === 'running') {
    pollTimer = setTimeout(() => poll(onDone), 1500)
    return
  }
  if (job.value.state === 'error') {
    error.value = job.value.error
    return
  }
  onDone(job.value.result)
}

async function startCheck() {
  error.value = null
  applied.value = null
  preview.value = null
  selected.value = new Set()
  try {
    job.value = await api.qearn.check()
  } catch (e) {
    error.value = e.message.startsWith('409') ? t('qearn.already_running') : e.message
    return
  }
  poll(result => { preview.value = result })
}

async function applyCorrections() {
  error.value = null
  try {
    job.value = await api.qearn.apply([...selected.value])
  } catch (e) {
    error.value = e.message.startsWith('409') ? t('qearn.already_running') : e.message
    return
  }
  poll(async result => {
    applied.value = result
    preview.value = null
    selected.value = new Set()
    await loadPositions()
  })
}

const candidates = computed(() => (preview.value?.wallets || []).flatMap(w => w.candidates.map(c => ({ ...c, wallet_id: w.wallet_id }))))

const previewSummary = computed(() => {
  const ws = preview.value?.wallets || []
  return {
    wallets: ws.length,
    locks: ws.reduce((a, w) => a + (w.missing_locks || 0), 0),
    payouts: ws.reduce((a, w) => a + (w.archive_imports || 0), 0),
    splits: ws.reduce((a, w) => a + (w.splits || 0), 0),
    stale: ws.reduce((a, w) => a + (w.stale_reconstructed?.length || 0), 0),
    issues: ws.flatMap(w => (w.issues || []).map(i => ({ ...i, wallet_id: w.wallet_id }))),
  }
})

const appliedSummary = computed(() => {
  const ws = applied.value?.wallets || []
  const sum = k => ws.reduce((a, w) => a + (w.applied?.[k] || 0), 0)
  return {
    locks: sum('locks_imported'), payouts: sum('payouts_imported'), reconstructed: sum('reconstructed'),
    removed: sum('removed'), splits: sum('splits'),
  }
})

function toggle(key) {
  const s = new Set(selected.value)
  s.has(key) ? s.delete(key) : s.add(key)
  selected.value = s
}

function toggleAll() {
  selected.value = selected.value.size === candidates.value.length
    ? new Set()
    : new Set(candidates.value.map(c => c.key))
}

function issueText(i) {
  if (i.code === 'no_yield') return t('qearn.issue_no_yield', { epoch: i.lock_epoch })
  if (i.code === 'unmatched_payout') return t('qearn.issue_unmatched', { amount: fmtQu(i.amount) })
  return t('qearn.issue_unknown_epoch', { tick: i.tick ?? '—' })
}

function startEdit(walletId, entry) {
  editingKey.value = `${walletId}|${entry.payout_event_id}`
  editValue.value = String(entry.interest ?? '')
}

async function saveInterest(walletId, entry) {
  const value = Number(String(editValue.value).replace(/[^\d]/g, ''))
  if (!Number.isFinite(value)) return
  savingInterest.value = true
  try {
    await api.qearn.setInterest(entry.payout_event_id, walletId, value)
    editingKey.value = null
    await loadPositions()
  } catch (e) {
    error.value = e.message
  } finally {
    savingInterest.value = false
  }
}

onMounted(async () => {
  await loadPositions()
  // resume a job that is still running (e.g. after switching tabs)
  try {
    const j = await api.qearn.job()
    if (j.state === 'running') {
      job.value = j
      poll(result => {
        if (j.kind === 'apply') { applied.value = result; loadPositions() } else { preview.value = result }
      })
    }
  } catch { /* ignore */ }
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="space-y-6">
    <!-- Intro + action -->
    <div class="card space-y-3">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('qearn.title') }}</h3>
      <p class="text-xs text-gray-500 leading-relaxed">{{ t('qearn.intro') }}</p>
      <p class="text-xs text-gray-500 leading-relaxed">{{ t('qearn.check_desc') }}</p>
      <div class="flex flex-wrap items-center gap-3 pt-1">
        <button class="btn text-sm" :disabled="running" @click="startCheck">
          {{ running ? t('qearn.running', { done: job?.progress?.done ?? 0, total: job?.progress?.total ?? 0 }) : t('qearn.check_btn') }}
        </button>
        <span v-if="running" class="text-xs text-gray-500">{{ t('qearn.running_hint') }}</span>
      </div>
      <p v-if="error" class="text-xs text-red-400">{{ t('common.error_prefix') }}{{ error }}</p>

      <!-- Result of the real run -->
      <div v-if="applied" class="rounded-lg border border-green-500/40 bg-green-500/10 px-4 py-3 text-xs text-green-300 space-y-1">
        <div class="font-semibold">✓ {{ t('qearn.applied_title') }}</div>
        <div>{{ t('qearn.applied_text', appliedSummary) }}</div>
        <div v-for="e in applied.errors" :key="e.wallet_id" class="text-red-400">{{ walletName(e.wallet_id) }}: {{ e.error }}</div>
      </div>
    </div>

    <!-- Preview (dry run) -->
    <div v-if="preview" class="card space-y-4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('qearn.preview_title') }}</h3>
      <p v-if="!preview.wallets.length" class="text-xs text-gray-500">{{ t('qearn.no_activity') }}</p>
      <template v-else>
        <ul class="text-xs text-gray-400 space-y-1 list-disc pl-5">
          <li>{{ t('qearn.preview_wallets', { count: previewSummary.wallets }) }}</li>
          <li>{{ t('qearn.preview_locks', { count: previewSummary.locks }) }}</li>
          <li>{{ t('qearn.preview_payouts', { count: previewSummary.payouts }) }}</li>
          <li>{{ t('qearn.preview_splits', { count: previewSummary.splits }) }}</li>
          <li v-if="previewSummary.stale">{{ t('qearn.preview_stale', { count: previewSummary.stale }) }}</li>
        </ul>

        <div v-if="previewSummary.issues.length" class="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-400 space-y-0.5">
          <div v-for="(i, idx) in previewSummary.issues" :key="idx">⚠ {{ walletName(i.wallet_id) }}: {{ issueText(i) }}</div>
        </div>

        <!-- Reconstruction candidates: explicit confirmation required -->
        <div v-if="candidates.length" class="space-y-2">
          <h4 class="text-xs font-semibold text-qubic-teal">{{ t('qearn.candidates_title') }}</h4>
          <p class="text-xs text-gray-500 leading-relaxed">{{ t('qearn.candidates_desc') }}</p>
          <div class="overflow-x-auto">
            <table class="table-std">
              <thead class="thead-std">
                <tr>
                  <th class="px-3 py-2 text-left">
                    <input type="checkbox" class="accent-qubic-teal" :checked="selected.size === candidates.length" @change="toggleAll" />
                  </th>
                  <th class="px-3 py-2 text-left">{{ t('qearn.col_wallet') }}</th>
                  <th class="px-3 py-2 text-left">{{ t('qearn.col_type') }}</th>
                  <th class="px-3 py-2 text-left whitespace-nowrap">{{ t('qearn.col_lock_epoch') }}</th>
                  <th class="px-3 py-2 text-left whitespace-nowrap">{{ t('qearn.col_payout_epoch') }}</th>
                  <th class="px-3 py-2 text-right">{{ t('qearn.col_principal') }}</th>
                  <th class="px-3 py-2 text-right">{{ t('qearn.col_interest') }}</th>
                  <th class="px-3 py-2 text-right">{{ t('qearn.col_payout') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in candidates" :key="c.key" class="tr-row cursor-pointer" @click="toggle(c.key)">
                  <td class="px-3 py-2"><input type="checkbox" class="accent-qubic-teal" :checked="selected.has(c.key)" @click.stop="toggle(c.key)" /></td>
                  <td class="px-3 py-2 text-gray-300 whitespace-nowrap">{{ walletName(c.wallet_id) }}</td>
                  <td class="px-3 py-2 text-gray-400 whitespace-nowrap">
                    {{ c.kind === 'EARLY' ? t('qearn.kind_early') : t('qearn.kind_full') }}
                    <span v-if="c.estimated" class="text-xs px-1 rounded bg-amber-500/20 text-amber-300 ml-1">{{ t('qearn.badge_estimated') }}</span>
                  </td>
                  <td class="px-3 py-2 font-mono text-gray-400">{{ c.lock_epoch }}</td>
                  <td class="px-3 py-2 font-mono text-gray-400">{{ c.payout_epoch }}</td>
                  <td class="px-3 py-2 text-right font-mono whitespace-nowrap">{{ fmtQu(c.principal) }}</td>
                  <td class="px-3 py-2 text-right font-mono whitespace-nowrap text-green-400">{{ fmtQu(c.interest) }}</td>
                  <td class="px-3 py-2 text-right font-mono whitespace-nowrap">{{ fmtQu(c.amount) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <button class="btn text-sm" :disabled="running" @click="applyCorrections">
            {{ t('qearn.apply_btn', { count: selected.size }) }}
          </button>
          <button class="btn-ghost text-sm" :disabled="running" @click="preview = null">{{ t('common.cancel') }}</button>
        </div>
        <p class="text-xs text-gray-500 leading-snug">{{ t('qearn.apply_hint') }}</p>
      </template>
    </div>

    <!-- Positions overview -->
    <div class="card space-y-4">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('qearn.positions_title') }}</h3>
        <div v-if="positions.length" class="text-xs text-gray-500 flex gap-4">
          <span>{{ t('qearn.total_locked') }}: <span class="font-mono text-sky-300">{{ fmtQu(totals.locked) }} QU</span></span>
          <span>{{ t('qearn.total_interest') }}: <span class="font-mono text-green-400">{{ fmtQu(totals.interest) }} QU</span></span>
        </div>
      </div>
      <p v-if="loadingPositions" class="text-xs text-gray-500">{{ t('common.loading') }}</p>
      <p v-else-if="!positions.length" class="text-xs text-gray-500">{{ t('qearn.no_positions') }}</p>

      <div v-for="[walletId, rows] in positionsByWallet" :key="walletId" class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ walletName(walletId) }}</h4>
        <div class="overflow-x-auto">
          <table class="table-std">
            <thead class="thead-std">
              <tr>
                <th class="px-3 py-2 text-left whitespace-nowrap">{{ t('qearn.col_lock_epoch') }}</th>
                <th class="px-3 py-2 text-left whitespace-nowrap">{{ t('qearn.col_payout_epoch') }}</th>
                <th class="px-3 py-2 text-right">{{ t('qearn.col_principal') }}</th>
                <th class="px-3 py-2 text-left">{{ t('qearn.col_status') }}</th>
                <th class="px-3 py-2 text-right">{{ t('qearn.col_payout') }}</th>
                <th class="px-3 py-2 text-right">{{ t('qearn.col_interest') }}</th>
                <th class="px-3 py-2 text-right">{{ t('qearn.col_rate') }}</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="p in rows" :key="p.lock_epoch">
                <tr class="tr-row">
                  <td class="px-3 py-2 font-mono text-gray-300">{{ p.lock_epoch }}</td>
                  <td class="px-3 py-2 font-mono text-gray-400">{{ p.end_epoch }}</td>
                  <td class="px-3 py-2 text-right font-mono whitespace-nowrap cursor-copy select-none" @dblclick.prevent="copyValue(p.principal)">{{ fmtQu(p.principal) }}</td>
                  <td class="px-3 py-2 whitespace-nowrap">
                    <span :class="['text-xs px-1.5 rounded', STATUS_CLASS[p.status] || 'text-gray-400']">{{ t(`qearn.status_${p.status}`) }}</span>
                    <span v-if="p.detail?.derived" class="text-xs text-gray-500 ml-1" :title="t('qearn.note_derived')">ⓘ</span>
                  </td>
                  <td class="px-3 py-2 text-right font-mono whitespace-nowrap">
                    {{ p.status === 'LOCKED' ? '~' + fmtQu(p.expected_payout) : fmtQu(p.payout ?? (p.status === 'MISSING' ? p.expected_payout : null)) }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono whitespace-nowrap text-green-400">
                    {{ p.status === 'LOCKED' || p.status === 'EARLY_UNLOCKED' ? '—' : fmtQu(p.interest) }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono whitespace-nowrap text-gray-400">
                    {{ p.status === 'LOCKED' ? '~' + fmtRate(p.expected_payout != null ? p.expected_payout - p.principal + p.early_unlocked : null, p.principal - p.early_unlocked)
                      : p.status === 'EARLY_UNLOCKED' ? '—' : fmtRate(p.interest, p.principal - p.early_unlocked) }}
                  </td>
                </tr>
                <!-- early unlocks of this round -->
                <tr v-for="e in p.detail?.early || []" :key="`${p.lock_epoch}-${e.tick}`" class="tr-row">
                  <td class="px-3 py-1.5 text-xs text-gray-500 pl-6" colspan="2">↳ {{ t('qearn.kind_early') }} · {{ t('qearn.early_pct', { pct: e.pct }) }}</td>
                  <td class="px-3 py-1.5 text-right font-mono text-xs whitespace-nowrap">{{ fmtQu(e.amount) }}</td>
                  <td class="px-3 py-1.5 whitespace-nowrap">
                    <span :class="['text-xs px-1.5 rounded', STATUS_CLASS[e.status] || 'text-gray-400']">{{ t(`qearn.status_${e.status}`) }}</span>
                    <span v-if="e.estimated" class="text-xs px-1 rounded bg-amber-500/20 text-amber-300 ml-1">{{ t('qearn.badge_estimated') }}</span>
                  </td>
                  <td class="px-3 py-1.5 text-right font-mono text-xs whitespace-nowrap">{{ e.interest != null ? fmtQu(e.amount + e.interest) : '—' }}</td>
                  <td class="px-3 py-1.5 text-right font-mono text-xs whitespace-nowrap text-green-400">
                    <template v-if="editingKey === `${walletId}|${e.payout_event_id}`">
                      <input v-model="editValue" class="input text-xs py-0.5 px-2 w-36 text-right"
                             @keyup.enter="saveInterest(walletId, e)" @keyup.esc="editingKey = null" />
                      <button class="icon-btn text-green-400 ml-1" :disabled="savingInterest" :title="t('common.save')" @click="saveInterest(walletId, e)">✓</button>
                    </template>
                    <template v-else>
                      {{ fmtQu(e.interest) }}
                      <button v-if="e.status === 'RECONSTRUCTED' && (e.estimated || e.override)"
                              class="icon-btn ml-1" :title="t('qearn.edit_interest')" @click="startEdit(walletId, e)">✎</button>
                    </template>
                  </td>
                  <td class="px-3 py-1.5 text-right font-mono text-xs whitespace-nowrap text-gray-400">{{ fmtRate(e.interest, e.amount) }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
      <p v-if="positions.length" class="text-xs text-gray-500">
        {{ t('qearn.last_check') }}: {{ fmtDate(positions[0]?.checked_at) }}
      </p>
    </div>

    <!-- Mini documentation -->
    <div class="card space-y-3">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('qearn.doc_title') }}</h3>
      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('qearn.doc_split_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('qearn.doc_split_text') }}</p>
      </div>
      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('qearn.doc_check_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('qearn.doc_check_text') }}</p>
      </div>
      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('qearn.doc_tax_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('qearn.doc_tax_text') }}</p>
      </div>
    </div>
  </div>
</template>

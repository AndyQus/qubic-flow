<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useTranslation } from 'i18next-vue'
import { api } from '../api'
import { useAppStore } from '../stores/app'
import PageLoader from './PageLoader.vue'

const { t } = useTranslation()
const store = useAppStore()

const settings = ref(null)
const loading = ref(true)
const series = ref('hourly')
const sheet = ref('overview')          // overview | owner:<name> | transfer | transactions
const data = ref(null)                 // overview response
const sheetRows = ref(null)            // owner/transfer/transactions response
const sheetOffset = ref(0)
const SHEET_PAGE = 200
const capturing = ref(false)
const error = ref('')

const seriesTabs = computed(() => {
  if (!settings.value) return []
  return [
    settings.value.hourly_enabled && 'hourly',
    settings.value.daily_enabled && 'daily',
    settings.value.weekly_enabled && 'weekly',
  ].filter(Boolean)
})

const owners = computed(() => data.value?.owners?.map(o => o.owner) ?? [])

const sheetOptions = computed(() => {
  const opts = [
    { value: 'overview', label: t('bhistory.sheet_overview') },
    { value: 'balances', label: t('bhistory.sheet_balances') },
  ]
  for (const o of owners.value) {
    opts.push({ value: `owner:${o}`, label: `Ledger ${o || t('bhistory.no_owner')}` })
  }
  opts.push({ value: 'transfer', label: t('bhistory.sheet_transfer') })
  opts.push({ value: 'transactions', label: t('bhistory.sheet_transactions') })
  return opts
})

const currency = computed(() => store.currency === 'USD' ? 'usd' : 'eur')
const currencySymbol = computed(() => store.currency === 'USD' ? '$' : '€')

function fmtAmount(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString(store.locale)
}

function fmtFiat(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString(store.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function fmtRatePerBln(row, cur) {
  const rate = cur === 'usd' ? row.usd_rate : row.eur_rate
  if (rate === null || rate === undefined) return '—'
  return fmtFiat(rate * 1e9)
}

function fmtShortDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d)) return iso
  return d.toLocaleDateString(store.locale, { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d)) return iso
  if (series.value === 'hourly') {
    return d.toLocaleString(store.locale, { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString(store.locale, { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function rowValue(row) {
  const rate = currency.value === 'usd' ? row.usd_rate : row.eur_rate
  if (rate === null || rate === undefined) return null
  let sum = 0
  for (const cell of Object.values(row.cells)) {
    if (cell.delta !== null && cell.delta !== undefined) sum += cell.delta
  }
  return sum * rate
}

function rowTotalDelta(row) {
  let sum = 0
  let any = false
  for (const cell of Object.values(row.cells)) {
    if (cell.delta !== null && cell.delta !== undefined) { sum += cell.delta; any = true }
  }
  return any ? sum : null
}

async function loadSettings() {
  settings.value = await api.balanceHistory.getSettings()
  if (!seriesTabs.value.includes(series.value) && seriesTabs.value.length) {
    series.value = seriesTabs.value[0]
  }
}

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.balanceHistory.overview(series.value)
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    loading.value = false
  }
}

async function loadSheet(reset = true) {
  loading.value = true
  error.value = ''
  try {
    if (reset) sheetOffset.value = 0
    let resp
    if (sheet.value.startsWith('owner:')) {
      resp = await api.balanceHistory.ownerLedger(sheet.value.slice(6), series.value, SHEET_PAGE, sheetOffset.value)
    } else if (sheet.value === 'transfer') {
      resp = await api.balanceHistory.transfers(SHEET_PAGE, sheetOffset.value)
    } else {
      resp = await api.balanceHistory.transactions(series.value, SHEET_PAGE, sheetOffset.value)
    }
    if (reset || !sheetRows.value) sheetRows.value = resp
    else sheetRows.value = { ...resp, rows: [...sheetRows.value.rows, ...resp.rows] }
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  sheetOffset.value += SHEET_PAGE
  await loadSheet(false)
}

async function reload() {
  if (sheet.value === 'overview' || sheet.value === 'balances') await loadOverview()
  else await loadSheet()
}

// ── Bestand (absolute balances) ─────────────────────────────────
// user-entered rows carry no balance and are hidden here
const balanceRows = computed(() =>
  (data.value?.rows ?? []).filter(r => Object.values(r.cells).some(c => c.balance !== null && c.balance !== undefined)))

function rowBalanceTotal(row) {
  let sum = 0
  for (const cell of Object.values(row.cells)) {
    if (cell.balance !== null && cell.balance !== undefined) sum += cell.balance
  }
  return sum
}

function rowBalanceValue(row) {
  const rate = currency.value === 'usd' ? row.usd_rate : row.eur_rate
  if (rate === null || rate === undefined) return null
  return rowBalanceTotal(row) * rate
}

// Consistency check: the balance delta must match the captured in-/outflows
// of the interval (both come from the network) — a mismatch is flagged.
function cellMismatch(cell) {
  if (!cell || cell.delta === null || cell.delta === undefined) return false
  if (cell.in_amount === null || cell.in_amount === undefined) return false
  if (cell.out_amount === null || cell.out_amount === undefined) return false
  return cell.delta !== (cell.in_amount - cell.out_amount)
}

onMounted(async () => {
  try {
    await loadSettings()
    await loadOverview()
  } catch (e) {
    error.value = String(e.message || e)
    loading.value = false
  }
})

watch(series, () => reload())
watch(sheet, () => reload())

// ── capture now ─────────────────────────────────────────────────
async function captureNow() {
  capturing.value = true
  error.value = ''
  try {
    await api.balanceHistory.capture(series.value)
    await loadOverview()
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    capturing.value = false
  }
}

// ── row editing (everything editable, edits are flagged) ───────
const editBucket = ref(null)
const editModel = ref(null)

function startEdit(row) {
  const cells = {}
  for (const [wid, cell] of Object.entries(row.cells)) {
    cells[wid] = { id: cell.id, delta: cell.delta, orig: cell.delta }
  }
  editModel.value = {
    why: row.why || '', info: row.info || '', note: row.note || '',
    origWhy: row.why || '', origInfo: row.info || '', origNote: row.note || '',
    cells,
  }
  editBucket.value = row.bucket
}

function cancelEdit() {
  editBucket.value = null
  editModel.value = null
}

async function saveEdit(row) {
  error.value = ''
  try {
    const m = editModel.value
    if (m.why !== m.origWhy || m.info !== m.origInfo || m.note !== m.origNote) {
      await api.balanceHistory.saveAnnotation({
        kind: series.value, bucket: row.bucket,
        why: m.why || null, info: m.info || null, note: m.note || null,
      })
    }
    for (const cell of Object.values(m.cells)) {
      const val = cell.delta === '' || cell.delta === null ? null : Number(cell.delta)
      if (val !== null && val !== cell.orig) {
        await api.balanceHistory.editSnapshot(cell.id, { delta: val })
      }
    }
    cancelEdit()
    await loadOverview()
  } catch (e) {
    error.value = String(e.message || e)
  }
}

async function deleteRow(row) {
  if (!confirm(t('bhistory.delete_confirm'))) return
  error.value = ''
  try {
    await api.balanceHistory.deleteRow(series.value, row.bucket)
    await loadOverview()
  } catch (e) {
    error.value = String(e.message || e)
  }
}

// ── manual new row ──────────────────────────────────────────────
const showNewRow = ref(false)
const newRow = ref(null)

function openNewRow() {
  newRow.value = {
    date: new Date().toISOString().slice(0, 10),
    epoch: null, why: '', info: '', note: '',
    cells: Object.fromEntries((data.value?.columns ?? []).map(c => [c.id, ''])),
  }
  showNewRow.value = true
}

async function saveNewRow() {
  error.value = ''
  const cells = {}
  for (const [wid, v] of Object.entries(newRow.value.cells)) {
    if (v !== '' && v !== null && !isNaN(Number(v))) cells[wid] = Number(v)
  }
  if (!Object.keys(cells).length) {
    error.value = t('bhistory.new_row_need_amount')
    return
  }
  try {
    await api.balanceHistory.createRow({
      kind: series.value,
      date: newRow.value.date,
      epoch: newRow.value.epoch ? Number(newRow.value.epoch) : null,
      why: newRow.value.why || null,
      info: newRow.value.info || null,
      note: newRow.value.note || null,
      cells,
    })
    showNewRow.value = false
    await loadOverview()
  } catch (e) {
    error.value = String(e.message || e)
  }
}

const exportHref = computed(() =>
  `/api/v1/balance-history/export/${series.value}?lang=${store.lang === 'de' ? 'de' : 'en'}`)

const seriesLabel = { hourly: 'bhistory.series_hourly', daily: 'bhistory.series_daily', weekly: 'bhistory.series_weekly' }
</script>

<template>
  <div class="space-y-3">

    <!-- Serie + Sheet + Aktionen -->
    <div class="card !py-2 !px-3 flex items-center flex-wrap gap-2">
      <div class="tab-group">
        <button v-for="s in seriesTabs" :key="s"
                :class="['tab-btn', series === s && 'tab-btn-active']"
                @click="series = s">{{ t(seriesLabel[s]) }}</button>
      </div>

      <select v-model="sheet" class="input text-xs py-1 pl-2 pr-8 cursor-pointer">
        <option v-for="o in sheetOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>

      <div class="flex items-center gap-2 ml-auto">
        <button v-if="sheet === 'overview'"
                class="btn text-xs py-1 px-3"
                :disabled="capturing"
                :title="t('bhistory.capture_hint')"
                @click="captureNow">
          <span v-if="capturing">{{ t('common.loading') }}</span>
          <span v-else>⚡ {{ t('bhistory.capture_now') }}</span>
        </button>
        <button v-if="sheet === 'overview'" class="btn-ghost text-xs py-1 px-3" @click="openNewRow">
          + {{ t('bhistory.new_row') }}
        </button>
        <a :href="exportHref" class="btn-ghost text-xs py-1 px-3" :title="t('bhistory.download_hint')">
          ⬇ {{ t('bhistory.download') }}
        </a>
      </div>
    </div>

    <div v-if="error" class="card p-3 text-xs text-red-400 border border-red-400/40">{{ error }}</div>

    <!-- Neuer manueller Datensatz -->
    <div v-if="showNewRow && newRow" class="card p-3 space-y-2">
      <p class="text-xs font-semibold text-gray-300">{{ t('bhistory.new_row_title') }}</p>
      <div class="flex flex-wrap gap-2 items-center">
        <label class="text-xs text-gray-400">{{ t('bhistory.col_date') }}
          <input v-model="newRow.date" type="date" class="input text-xs py-1 ml-1" />
        </label>
        <label class="text-xs text-gray-400">{{ t('bhistory.col_epoch') }}
          <input v-model="newRow.epoch" type="number" class="input text-xs py-1 w-20 ml-1" />
        </label>
        <label class="text-xs text-gray-400">why
          <input v-model="newRow.why" class="input text-xs py-1 w-32 ml-1" />
        </label>
        <label class="text-xs text-gray-400 grow">{{ t('bhistory.col_info') }}
          <input v-model="newRow.info" class="input text-xs py-1 w-full ml-1" />
        </label>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <label v-for="c in data?.columns ?? []" :key="c.id" class="text-xs text-gray-400">
          {{ c.label }}
          <input v-model="newRow.cells[c.id]" type="number" class="input text-xs py-1 w-full"
                 :placeholder="t('bhistory.delta_placeholder')" />
        </label>
      </div>
      <div class="flex gap-2">
        <button class="btn text-xs py-1 px-3" @click="saveNewRow">{{ t('common.save') }}</button>
        <button class="btn-ghost text-xs py-1 px-3" @click="showNewRow = false">{{ t('common.cancel') }}</button>
      </div>
    </div>

    <PageLoader v-if="loading" />

    <!-- ============ ÜBERSICHT (Ledger) ============ -->
    <div v-else-if="sheet === 'overview'" class="card p-0 overflow-x-auto">
      <div v-if="!data?.rows?.length" class="p-6 text-center text-gray-500 text-xs">
        {{ t('bhistory.no_data') }}
      </div>
      <table v-else class="w-full text-xs whitespace-nowrap">
        <thead>
          <tr class="text-gray-500 border-b border-qubic-border">
            <th colspan="9"></th>
            <th v-for="grp in data.owners" :key="grp.owner"
                :colspan="grp.wallet_ids.length"
                class="px-2 py-1 text-center font-semibold text-qubic-teal/80 border-l border-qubic-border">
              {{ grp.owner || t('bhistory.no_owner') }}
            </th>
            <th colspan="3"></th>
          </tr>
          <tr class="text-left text-gray-400 border-b border-qubic-border">
            <th class="px-2 py-1.5">{{ t('bhistory.col_date') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_epoch') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_from') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_to') }}</th>
            <th class="px-2 py-1.5">€ = 1Bln</th>
            <th class="px-2 py-1.5">$ = 1Bln</th>
            <th class="px-2 py-1.5">why</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_total') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_value') }} {{ currencySymbol }}</th>
            <th v-for="c in data.columns" :key="c.id"
                class="px-2 py-1.5 text-right border-l border-qubic-border/50" :title="c.id">
              {{ c.label }}
            </th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_info') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_note') }}</th>
            <th class="px-2 py-1.5"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in data.rows" :key="row.bucket"
              class="border-b border-qubic-border/40 hover:bg-qubic-teal/5">
            <template v-if="editBucket !== row.bucket">
              <td class="px-2 py-1.5 font-mono">
                {{ fmtDate(row.captured_at) }}
                <span v-if="row.trigger === 'manual'" class="ml-1 text-amber-400" :title="t('bhistory.trigger_manual')">⚡</span>
                <span v-else-if="row.trigger === 'user'" class="ml-1 text-sky-400" :title="t('bhistory.trigger_user')">✎</span>
              </td>
              <td class="px-2 py-1.5 font-mono">{{ row.epoch ?? '—' }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtShortDate(row.range_from) }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtShortDate(row.range_to) }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtRatePerBln(row, 'eur') }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtRatePerBln(row, 'usd') }}</td>
              <td class="px-2 py-1.5">{{ row.why || '' }}</td>
              <td class="px-2 py-1.5 font-mono text-right"
                  :class="(rowTotalDelta(row) ?? 0) < 0 ? 'text-red-400' : 'text-emerald-400'">
                {{ fmtAmount(rowTotalDelta(row)) }}
              </td>
              <td class="px-2 py-1.5 font-mono text-right">{{ fmtFiat(rowValue(row)) }}</td>
              <td v-for="c in data.columns" :key="c.id"
                  class="px-2 py-1.5 font-mono text-right border-l border-qubic-border/30"
                  :class="(row.cells[c.id]?.delta ?? 0) < 0 ? 'text-red-400' : ''">
                <template v-if="row.cells[c.id]">
                  {{ fmtAmount(row.cells[c.id].delta) }}<span v-if="row.cells[c.id].edited"
                        class="text-amber-400 ml-0.5" :title="t('bhistory.edited_hint')">*</span>
                </template>
                <template v-else>—</template>
              </td>
              <td class="px-2 py-1.5 max-w-[16rem] truncate" :title="row.info || ''">{{ row.info || '' }}</td>
              <td class="px-2 py-1.5 max-w-[12rem] truncate" :title="row.note || ''">{{ row.note || '' }}</td>
              <td class="px-2 py-1.5 text-right">
                <button class="btn-ghost text-xs py-0.5 px-1.5" :title="t('common.save')" @click="startEdit(row)">✎</button>
                <button v-if="row.trigger === 'user'"
                        class="btn-ghost text-xs py-0.5 px-1.5 text-red-400"
                        :title="t('wallet.delete')" @click="deleteRow(row)">🗑</button>
              </td>
            </template>
            <template v-else>
              <td class="px-2 py-1.5 font-mono">{{ fmtDate(row.captured_at) }}</td>
              <td class="px-2 py-1.5 font-mono">{{ row.epoch ?? '—' }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtShortDate(row.range_from) }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtShortDate(row.range_to) }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtRatePerBln(row, 'eur') }}</td>
              <td class="px-2 py-1.5 font-mono">{{ fmtRatePerBln(row, 'usd') }}</td>
              <td class="px-2 py-1.5">
                <input v-model="editModel.why" class="input text-xs py-0.5 w-24" placeholder="why" />
              </td>
              <td class="px-2 py-1.5"></td>
              <td class="px-2 py-1.5"></td>
              <td v-for="c in data.columns" :key="c.id" class="px-1 py-1 border-l border-qubic-border/30">
                <input v-if="editModel.cells[c.id]"
                       v-model="editModel.cells[c.id].delta"
                       type="number" class="input text-xs py-0.5 w-24 text-right" />
              </td>
              <td class="px-2 py-1.5">
                <input v-model="editModel.info" class="input text-xs py-0.5 w-40" />
              </td>
              <td class="px-2 py-1.5">
                <input v-model="editModel.note" class="input text-xs py-0.5 w-32" />
              </td>
              <td class="px-2 py-1.5 text-right whitespace-nowrap">
                <button class="btn text-xs py-0.5 px-1.5" @click="saveEdit(row)">✓</button>
                <button class="btn-ghost text-xs py-0.5 px-1.5" @click="cancelEdit">✕</button>
              </td>
            </template>
          </tr>
        </tbody>
        <tfoot>
          <tr class="border-t border-qubic-border text-gray-300 font-semibold">
            <td class="px-2 py-1.5" colspan="7">{{ t('bhistory.col_total') }}</td>
            <td class="px-2 py-1.5 font-mono text-right">
              {{ fmtAmount(Object.values(data.totals).reduce((a, b) => a + b, 0)) }}
            </td>
            <td class="px-2 py-1.5"></td>
            <td v-for="c in data.columns" :key="c.id"
                class="px-2 py-1.5 font-mono text-right border-l border-qubic-border/30"
                :class="(data.totals[c.id] ?? 0) < 0 ? 'text-red-400' : ''">
              {{ fmtAmount(data.totals[c.id] ?? 0) }}
            </td>
            <td colspan="3"></td>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- ============ BESTAND (absolute Balances) ============ -->
    <div v-else-if="sheet === 'balances'" class="card p-0 overflow-x-auto">
      <div v-if="!balanceRows.length" class="p-6 text-center text-gray-500 text-xs">
        {{ t('bhistory.no_data') }}
      </div>
      <table v-else class="w-full text-xs whitespace-nowrap">
        <thead>
          <tr class="text-gray-500 border-b border-qubic-border">
            <th colspan="2"></th>
            <th v-for="grp in data.owners" :key="grp.owner"
                :colspan="grp.wallet_ids.length"
                class="px-2 py-1 text-center font-semibold text-qubic-teal/80 border-l border-qubic-border">
              {{ grp.owner || t('bhistory.no_owner') }}
            </th>
            <th colspan="2"></th>
          </tr>
          <tr class="text-left text-gray-400 border-b border-qubic-border">
            <th class="px-2 py-1.5">{{ t('bhistory.col_date') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_epoch') }}</th>
            <th v-for="c in data.columns" :key="c.id"
                class="px-2 py-1.5 text-right border-l border-qubic-border/50" :title="c.id">
              {{ c.label }}
            </th>
            <th class="px-2 py-1.5 text-right">{{ t('bhistory.col_total') }}</th>
            <th class="px-2 py-1.5 text-right">{{ t('bhistory.col_value') }} {{ currencySymbol }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in balanceRows" :key="row.bucket"
              class="border-b border-qubic-border/40 hover:bg-qubic-teal/5">
            <td class="px-2 py-1.5 font-mono">
              {{ fmtDate(row.captured_at) }}
              <span v-if="row.trigger === 'manual'" class="ml-1 text-amber-400" :title="t('bhistory.trigger_manual')">⚡</span>
            </td>
            <td class="px-2 py-1.5 font-mono">{{ row.epoch ?? '—' }}</td>
            <td v-for="c in data.columns" :key="c.id"
                class="px-2 py-1.5 font-mono text-right border-l border-qubic-border/30">
              <template v-if="row.cells[c.id] && row.cells[c.id].balance !== null">
                <span :title="row.cells[c.id].tick ? 'Tick ' + row.cells[c.id].tick : ''">
                  {{ fmtAmount(row.cells[c.id].balance) }}
                </span>
                <span v-if="cellMismatch(row.cells[c.id])"
                      class="text-amber-400 ml-0.5 cursor-help"
                      :title="t('bhistory.check_mismatch')">⚠</span>
              </template>
              <template v-else>—</template>
            </td>
            <td class="px-2 py-1.5 font-mono text-right font-semibold">{{ fmtAmount(rowBalanceTotal(row)) }}</td>
            <td class="px-2 py-1.5 font-mono text-right">{{ fmtFiat(rowBalanceValue(row)) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ============ LEDGER JE BESITZER ============ -->
    <div v-else-if="sheet.startsWith('owner:')" class="card p-0 overflow-x-auto">
      <div v-if="!sheetRows?.rows?.length" class="p-6 text-center text-gray-500 text-xs">
        {{ t('bhistory.no_data') }}
      </div>
      <table v-else class="w-full text-xs whitespace-nowrap">
        <thead>
          <tr class="text-left text-gray-400 border-b border-qubic-border">
            <th class="px-2 py-1.5">{{ t('bhistory.col_date') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_epoch') }}</th>
            <th class="px-2 py-1.5">why</th>
            <th v-for="w in sheetRows.wallets" :key="w.id"
                class="px-2 py-1.5 text-right border-l border-qubic-border/50" :title="w.id">
              {{ w.label }} <span class="text-gray-500 font-mono font-normal">{{ w.id.slice(0, 5) }}…</span>
            </th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_note') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sheetRows.rows" :key="(row.tx_id || 'agg') + row.timestamp"
              class="border-b border-qubic-border/40">
            <td class="px-2 py-1.5 font-mono">{{ fmtDate(row.timestamp) }}</td>
            <td class="px-2 py-1.5 font-mono">{{ row.epoch ?? '—' }}</td>
            <td class="px-2 py-1.5">
              {{ row.type === 'aggregate' ? t('bhistory.cat_reward') : (row.comment || (row.is_internal ? t('bhistory.cat_internal') : row.incoming ? t('stats.incoming') : t('stats.outgoing'))) }}
            </td>
            <td v-for="w in sheetRows.wallets" :key="w.id"
                class="px-2 py-1.5 font-mono text-right border-l border-qubic-border/30"
                :class="(row.cells[w.id] ?? 0) < 0 ? 'text-red-400' : 'text-emerald-400'">
              {{ row.cells[w.id] !== undefined ? fmtAmount(row.cells[w.id]) : '—' }}
            </td>
            <td class="px-2 py-1.5 max-w-[14rem] truncate"
                :title="row.type === 'aggregate' ? t('bhistory.residual_note') : (row.note || '')">
              {{ row.type === 'aggregate' ? t('bhistory.residual_note') : (row.note || '') }}
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="sheetRows && sheetRows.rows.length < sheetRows.total" class="p-2 text-center">
        <button class="btn-ghost text-xs py-1 px-3" @click="loadMore">{{ t('bhistory.load_more') }}</button>
      </div>
    </div>

    <!-- ============ TRANSFER ============ -->
    <div v-else-if="sheet === 'transfer'" class="card p-0 overflow-x-auto">
      <div v-if="!sheetRows?.rows?.length" class="p-6 text-center text-gray-500 text-xs">
        {{ t('bhistory.no_data') }}
      </div>
      <table v-else class="w-full text-xs whitespace-nowrap">
        <thead>
          <tr class="text-left text-gray-400 border-b border-qubic-border">
            <th class="px-2 py-1.5">{{ t('bhistory.col_date') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_epoch') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.transfer_from') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.transfer_to') }}</th>
            <th class="px-2 py-1.5 text-right">{{ t('event.amount') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sheetRows.rows" :key="row.id" class="border-b border-qubic-border/40">
            <td class="px-2 py-1.5 font-mono">{{ fmtDate(row.timestamp) }}</td>
            <td class="px-2 py-1.5 font-mono">{{ row.epoch ?? '—' }}</td>
            <td class="px-2 py-1.5">{{ row.source_label || row.source?.slice(0, 8) + '…' }}</td>
            <td class="px-2 py-1.5">{{ row.destination_label || row.destination?.slice(0, 8) + '…' }}</td>
            <td class="px-2 py-1.5 font-mono text-right">{{ fmtAmount(row.amount) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="sheetRows && sheetRows.rows.length < sheetRows.total" class="p-2 text-center">
        <button class="btn-ghost text-xs py-1 px-3" @click="loadMore">{{ t('bhistory.load_more') }}</button>
      </div>
    </div>

    <!-- ============ TRANSAKTIONEN ============ -->
    <div v-else class="card p-0 overflow-x-auto">
      <div v-if="!sheetRows?.rows?.length" class="p-6 text-center text-gray-500 text-xs">
        {{ t('bhistory.no_data') }}
      </div>
      <table v-else class="w-full text-xs whitespace-nowrap">
        <thead>
          <tr class="text-left text-gray-400 border-b border-qubic-border">
            <th class="px-2 py-1.5">{{ t('bhistory.col_date') }}</th>
            <th class="px-2 py-1.5">{{ t('event.type') }}</th>
            <th class="px-2 py-1.5 text-right">{{ t('event.amount') }}</th>
            <th class="px-2 py-1.5 text-right">{{ t('event.rate') }} {{ currencySymbol }}</th>
            <th class="px-2 py-1.5 text-right">{{ t('bhistory.col_value') }} {{ currencySymbol }}</th>
            <th class="px-2 py-1.5">{{ t('filter.owner') }}</th>
            <th class="px-2 py-1.5">{{ t('event.wallet') }}</th>
            <th class="px-2 py-1.5">{{ t('bhistory.col_text') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in sheetRows.rows" :key="(row.id || 'ev') + row.wallet_id + row.timestamp"
              class="border-b border-qubic-border/40">
            <td class="px-2 py-1.5 font-mono">{{ fmtDate(row.timestamp) }}</td>
            <td class="px-2 py-1.5">
              <span :class="row.source_type === 'EVENT' ? 'text-violet-400' : 'text-sky-400'"
                    :title="row.source_type === 'EVENT' ? t('bhistory.residual_note') : ''">
                {{ row.source_type === 'EVENT' ? t('event.badge_event') : t('event.badge_tx') }}
              </span>
            </td>
            <td class="px-2 py-1.5 font-mono text-right" :class="row.amount < 0 ? 'text-red-400' : 'text-emerald-400'">
              {{ fmtAmount(row.amount) }}
            </td>
            <td class="px-2 py-1.5 font-mono text-right">
              {{ (currency === 'usd' ? row.usd_rate : row.eur_rate)?.toFixed(10) ?? '—' }}
            </td>
            <td class="px-2 py-1.5 font-mono text-right">
              {{ fmtFiat(row.amount * (currency === 'usd' ? row.usd_rate : row.eur_rate)) }}
            </td>
            <td class="px-2 py-1.5">{{ row.owner || '—' }}</td>
            <td class="px-2 py-1.5" :title="row.wallet_id">{{ row.wallet_label || row.wallet_id?.slice(0, 5) + '…' }}</td>
            <td class="px-2 py-1.5 max-w-[16rem] truncate" :title="row.comment || ''">{{ row.comment || '' }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="sheetRows && sheetRows.rows.length < sheetRows.total" class="p-2 text-center">
        <button class="btn-ghost text-xs py-1 px-3" @click="loadMore">{{ t('bhistory.load_more') }}</button>
      </div>
    </div>

  </div>
</template>

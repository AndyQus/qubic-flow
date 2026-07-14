<script setup>
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import i18next from 'i18next'
import { api } from '../api'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '../components/PageHeader.vue'

const store = useAppStore()
const { t } = useTranslation()
const route = useRoute()
const router = useRouter()

const TABS = ['display', 'tax', 'data', 'bhistory']
function normalizeTab(q) { return TABS.includes(q) ? q : 'display' }
const activeTab = ref(normalizeTab(route.query.tab))

watch(() => route.query.tab, (q) => { activeTab.value = normalizeTab(q) })

function setActiveTab(tab) {
  router.push({ path: '/settings', query: tab === 'display' ? {} : { tab } })
}

// Tax settings
const taxSettings = ref({
  country: 'DE',
  method: 'FIFO',
  name: '',
  tax_id: '',
  address: '',
  company_name: '',
  company_tax_nr: '',
  company_vat: '',
  company_reg: '',
  company_address: '',
  fiscal_year: 'jan',
})
const taxCountries = ref({})
const taxSaving = ref(false)
const taxSaved = ref(false)
const loadError = ref(null)

// Some countries mandate a specific cost-basis method (e.g. DK → FIFO)
const forcedMethod = computed(() => taxCountries.value[taxSettings.value.country]?.forced_method || null)
watch(forcedMethod, (m) => { if (m) taxSettings.value.method = m })

onMounted(async () => {
  try {
    const [s, c, n, bh] = await Promise.all([
      api.tax.getSettings(),
      api.tax.getCountries(),
      api.notifications.getSettings().catch(() => null),
      api.balanceHistory.getSettings().catch(() => null),
    ])
    if (s) Object.assign(taxSettings.value, s)
    if (c) taxCountries.value = c
    if (n) Object.assign(notifySettings.value, n)
    if (bh) Object.assign(bhSettings.value, bh)
  } catch (e) {
    loadError.value = e.message
  }
})

// Bestandsverlauf (balance history) capture settings
const bhSettings = ref({
  hourly_enabled: true, daily_enabled: true, weekly_enabled: true,
  excel_autoexport: true, hourly_retention_days: 0, export_lang: 'de',
})
const bhSaving = ref(false)
const bhSaved = ref(false)
const bhRebuilding = ref(false)
const bhRebuilt = ref(null)

async function saveBhSettings() {
  bhSaving.value = true
  bhSaved.value = false
  try {
    const s = bhSettings.value
    const saved = await api.balanceHistory.saveSettings({
      bh_hourly_enabled: s.hourly_enabled,
      bh_daily_enabled: s.daily_enabled,
      bh_weekly_enabled: s.weekly_enabled,
      bh_excel_autoexport: s.excel_autoexport,
      bh_hourly_retention_days: Number(s.hourly_retention_days) || 0,
      bh_export_lang: store.lang === 'de' ? 'de' : 'en',
    })
    Object.assign(bhSettings.value, saved)
    bhSaved.value = true
    setTimeout(() => { bhSaved.value = false }, 2500)
  } catch (e) {
    loadError.value = e.message
  } finally {
    bhSaving.value = false
  }
}

async function rebuildBhExports() {
  bhRebuilding.value = true
  bhRebuilt.value = null
  try {
    const r = await api.balanceHistory.rebuildExports()
    bhRebuilt.value = r.written?.length ?? 0
  } catch (e) {
    loadError.value = e.message
  } finally {
    bhRebuilding.value = false
  }
}

const bhResetting = ref(null)          // kind currently being reset
const bhResetResult = ref(null)        // { kind, deleted } of the last reset

async function resetBhSeries(kind) {
  const label = t(`bhistory.series_${kind}`)
  if (!confirm(t('settings.bh_reset_confirm').replace('{series}', label))) return
  bhResetting.value = kind
  bhResetResult.value = null
  try {
    const r = await api.balanceHistory.resetSeries(kind)
    bhResetResult.value = r
  } catch (e) {
    loadError.value = e.message
  } finally {
    bhResetting.value = null
  }
}

// Webhook notifications
const notifySettings = ref({ enabled: false, webhook_url: '', format: 'generic', min_amount: 0, notify_tx: true, notify_event: true })
const notifySaving = ref(false)
const notifySaved = ref(false)
const notifyTesting = ref(false)
const notifyTestResult = ref(null)

async function saveNotifySettings() {
  notifySaving.value = true
  notifySaved.value = false
  notifyTestResult.value = null
  try {
    await api.notifications.saveSettings(notifySettings.value)
    notifySaved.value = true
    setTimeout(() => { notifySaved.value = false }, 3000)
  } finally {
    notifySaving.value = false
  }
}

async function testNotification() {
  notifyTesting.value = true
  notifyTestResult.value = null
  try {
    // Save first so the backend tests exactly what is configured
    await api.notifications.saveSettings(notifySettings.value)
    const r = await api.notifications.test()
    notifyTestResult.value = !!r?.ok
  } catch {
    notifyTestResult.value = false
  } finally {
    notifyTesting.value = false
  }
}

async function saveTaxSettings() {
  taxSaving.value = true
  taxSaved.value = false
  try {
    await api.tax.saveSettings(taxSettings.value)
    taxSaved.value = true
    setTimeout(() => { taxSaved.value = false }, 3000)
  } finally {
    taxSaving.value = false
  }
}

function setLang(l) {
  store.setLang(l)
  i18next.changeLanguage(l)
}

const previewRows = ref([
  { id: 'p1', time: '18:42:01', direction: 'IN',  amount: '5.000', isNew: false },
  { id: 'p2', time: '18:40:55', direction: 'OUT', amount: '1.200', isNew: false },
  { id: 'p3', time: '18:39:10', direction: 'IN',  amount: '320',   isNew: false },
])

const previewAnimClass = computed(() => {
  if (store.animation === 'push-down') return 'anim-push-down'
  if (store.animation === 'slide-in') return 'anim-slide-in'
  return 'anim-beam-drop'
})

// DB Export
const dbExporting = ref(false)
const dbExportError = ref(null)

async function exportDbJson() {
  dbExporting.value = true
  dbExportError.value = null
  try {
    const data = await api.backup.export()
    const json = JSON.stringify(data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'qubicflow-backup.json'
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    dbExportError.value = err.message
  } finally {
    dbExporting.value = false
  }
}

// DB Restore
const dbRestoring = ref(false)
const dbRestoreResult = ref(null)
const dbRestoreInput = ref(null)

function triggerDbRestore() {
  dbRestoreInput.value?.click()
}

async function handleDbRestore(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.size > 500 * 1024 * 1024) {
    dbRestoreResult.value = { error: t('settings.db_restore_too_large') }
    e.target.value = ''
    return
  }
  dbRestoring.value = true
  dbRestoreResult.value = null
  try {
    const text = await file.text()
    const payload = JSON.parse(text)
    const result = await api.backup.restore(payload)
    dbRestoreResult.value = result
  } catch (err) {
    dbRestoreResult.value = { error: err.message }
  } finally {
    dbRestoring.value = false
    e.target.value = ''
  }
}

// Import from Qubic Ledger
const ledgerImporting = ref(false)
const ledgerImportResult = ref(null)
const ledgerFileInput = ref(null)

function triggerLedgerImport() {
  ledgerFileInput.value?.click()
}

async function handleLedgerFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  ledgerImporting.value = true
  ledgerImportResult.value = null
  try {
    const text = await file.text()
    const entries = JSON.parse(text)
    const existingIds = new Set(store.wallets.map(w => w.id))
    let created = 0, skipped = 0, failed = 0
    for (const entry of entries) {
      if (existingIds.has(entry.PublicId)) { skipped++; continue }
      const walletType = (entry.Zielgruppe === 'Company' || entry.Zielgruppe === 1) ? 'BUSINESS' : 'PRIVATE'
      try {
        await api.wallets.create({ id: entry.PublicId, label: entry.Besitzer, owner: entry.Besitzer, wallet_type: walletType, note: '', function: '' })
        created++
      } catch (err) {
        if (err.message.startsWith('409')) skipped++
        else failed++
      }
    }
    ledgerImportResult.value = { created, skipped, failed }
  } catch (err) {
    ledgerImportResult.value = { error: err.message }
  } finally {
    ledgerImporting.value = false
    e.target.value = ''
  }
}

// Re-fetch all events + TX for all wallets
const resyncing = ref(false)
const resyncResult = ref(null)

async function resyncAllData() {
  if (!confirm(t('settings.resync_confirm'))) return
  resyncing.value = true
  resyncResult.value = null
  try {
    const res = await api.wallets.resyncAll()
    resyncResult.value = { count: res?.wallets_queued ?? 0 }
  } catch (err) {
    resyncResult.value = { error: err.message }
  } finally {
    resyncing.value = false
  }
}

function simulate() {
  const dir = Math.random() > 0.5 ? 'IN' : 'OUT'
  const amount = (Math.floor(Math.random() * 9000) + 500).toLocaleString(store.locale)
  const now = new Date().toLocaleTimeString(store.locale)
  const newRow = { id: `p${Date.now()}`, time: now, direction: dir, amount, isNew: true }
  previewRows.value.unshift(newRow)
  if (previewRows.value.length > 3) previewRows.value.pop()
  setTimeout(() => {
    const row = previewRows.value.find(r => r.id === newRow.id)
    if (row) row.isNew = false
  }, 20_000)

  // Trigger Geldanimation-Vorschau
  const fakeId = `preview_${Date.now()}`
  store.newEventIds.push(fakeId)
  setTimeout(() => {
    const idx = store.newEventIds.indexOf(fakeId)
    if (idx >= 0) store.newEventIds.splice(idx, 1)
  }, 200)
}
</script>

<template>
  <div class="space-y-3">
  <PageHeader :title="t('nav.settings')" :hint="t('page_hint.settings')">
    <div class="tab-group">
      <button :class="['tab-btn', activeTab === 'display' && 'tab-btn-active']"
              @click="setActiveTab('display')">{{ t('settings.tab_display') }}</button>
      <button :class="['tab-btn', activeTab === 'tax' && 'tab-btn-active']"
              @click="setActiveTab('tax')">{{ t('settings.tab_tax') }}</button>
      <button :class="['tab-btn', activeTab === 'data' && 'tab-btn-active']"
              @click="setActiveTab('data')">{{ t('settings.tab_data') }}</button>
      <button :class="['tab-btn', activeTab === 'bhistory' && 'tab-btn-active']"
              @click="setActiveTab('bhistory')">{{ t('settings.tab_bhistory') }}</button>
    </div>
  </PageHeader>

  <!-- Tab: Darstellung (inkl. Animation) -->
  <div v-if="activeTab === 'display'" class="grid grid-cols-1 sm:grid-cols-2 gap-6">
    <!-- Darstellung -->
    <div class="card space-y-4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.display') }}</h3>

      <div class="flex items-center gap-4">
        <span class="text-sm text-gray-400 w-28 shrink-0">{{ t('settings.currency') }}</span>
        <div class="flex gap-2">
          <button v-for="[val, lbl, flag] in [['EUR','Euro','€'],['USD','US-Dollar','$']]"
                  :key="val"
                  :class="['btn-ghost text-sm py-2', store.currency === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                  @click="store.setCurrency(val)">
            <span class="mr-1">{{ flag }}</span>{{ lbl }}
          </button>
        </div>
      </div>

      <div class="flex items-center gap-4">
        <span class="text-sm text-gray-400 w-28 shrink-0">{{ t('settings.font_size') }}</span>
        <div class="flex items-center gap-2 flex-wrap">
          <button v-for="[val, lbl] in [['100', t('settings.font_sm')],['115', t('settings.font_md')],['130', t('settings.font_lg')]]"
                  :key="val"
                  :class="['btn-ghost text-sm py-2', store.fontSize === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                  @click="store.setFontSize(val)">
            {{ lbl }}
          </button>
          <span class="text-xs text-gray-500 ml-1">{{ store.fontSize }}%</span>
        </div>
      </div>

      <div class="flex items-center gap-4">
        <span class="text-sm text-gray-400 w-28 shrink-0">{{ t('settings.theme') }}</span>
        <div class="flex gap-2">
          <button :class="['btn-ghost text-sm py-2', store.theme === 'dark' && 'bg-qubic-teal/20 border-qubic-teal']"
                  @click="store.setTheme('dark')">{{ t('settings.dark') }}</button>
          <button :class="['btn-ghost text-sm py-2', store.theme === 'light' && 'bg-qubic-teal/20 border-qubic-teal']"
                  @click="store.setTheme('light')">{{ t('settings.light') }}</button>
        </div>
      </div>

      <div class="flex items-center gap-4">
        <span class="text-sm text-gray-400 w-28 shrink-0">{{ t('settings.language') }}</span>
        <div class="flex gap-2">
          <button :class="['btn-ghost text-sm py-2', store.lang === 'de' && 'bg-qubic-teal/20 border-qubic-teal']"
                  @click="setLang('de')">Deutsch</button>
          <button :class="['btn-ghost text-sm py-2', store.lang === 'en' && 'bg-qubic-teal/20 border-qubic-teal']"
                  @click="setLang('en')">English</button>
        </div>
      </div>
    </div>

    <!-- Eingangsanimation -->
    <div class="card">
      <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('moneyAnim.title') }}</h3>
      <div class="flex flex-wrap gap-2 mb-3">
        <button v-for="[val, key] in [['none','none'],['coin-rain','coin_rain'],['money-burst','money_burst'],['floating-coins','floating_coins']]"
                :key="val"
                :class="['btn-ghost text-sm py-2', store.moneyAnim === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                @click="store.setMoneyAnim(val)">
          {{ t(`moneyAnim.${key}`) }}
        </button>
        <button class="btn ml-auto" @click="simulate">▶ {{ t('settings.preview') }}</button>
      </div>
      <div class="flex gap-2 mb-4">
        <button :class="['btn-ghost text-sm py-2', store.moneySound && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                @click="store.setMoneySound(true)">
          🔔 {{ t('moneyAnim.sound') }}
        </button>
        <button :class="['btn-ghost text-sm py-2', !store.moneySound && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                @click="store.setMoneySound(false)">
          🔕 {{ t('moneyAnim.mute') }}
        </button>
      </div>
      <div v-if="store.moneySound" class="flex flex-wrap gap-2">
        <button v-for="[val, lbl] in [['kaching', t('moneyAnim.sound_kaching')],['coins', t('moneyAnim.sound_coins')],['chime', t('moneyAnim.sound_chime')]]"
                :key="val"
                :class="['btn-ghost text-sm py-2', store.soundStyle === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                @click="store.setSoundStyle(val)">
          {{ lbl }}
        </button>
      </div>

      <!-- Live-Vorschau -->
      <div class="rounded-lg border border-qubic-border overflow-hidden bg-qubic-bg/50 text-xs mt-3">
        <div class="flex border-b border-qubic-border text-gray-500 uppercase px-3 py-1.5">
          <span class="w-20">{{ t('common.time') }}</span>
          <span class="w-16">{{ t('event.direction') }}</span>
          <span class="font-mono">{{ t('event.amount') }}</span>
        </div>
        <div v-for="row in previewRows" :key="row.id"
             :class="[
               row.isNew ? previewAnimClass : '',
               row.isNew && row.direction === 'IN'  ? 'flash-in'  : '',
               row.isNew && row.direction === 'OUT' ? 'flash-out' : '',
               'flex items-center px-3 py-2 border-b border-qubic-border/30'
             ]">
          <span class="w-20 text-gray-400">{{ row.time }}</span>
          <span class="w-16">
            <span v-if="row.direction === 'IN'"  class="text-green-400">▲ IN</span>
            <span v-else                          class="text-red-400">▼ OUT</span>
          </span>
          <span class="font-mono">{{ row.amount }} QU</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Tab: Daten -->
  <div v-if="activeTab === 'data'" class="grid grid-cols-1 sm:grid-cols-2 gap-6">
    <!-- Export & Import Panel -->
    <div class="card space-y-4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.io_title') }}</h3>

      <!-- QubicFlow Backup Export -->
      <div class="space-y-2">
        <p class="text-xs font-semibold text-gray-300">{{ t('settings.db_export_label') }}</p>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('settings.db_export_desc') }}</p>
        <button class="btn text-sm" :disabled="dbExporting" @click="exportDbJson">
          {{ dbExporting ? t('common.loading') : t('settings.db_export_btn') }}
        </button>
        <p v-if="dbExportError" class="text-xs text-red-400">{{ t('common.error_prefix') }}{{ dbExportError }}</p>
      </div>

      <div class="border-t border-qubic-border/40"></div>

      <!-- QubicFlow Backup Restore -->
      <div class="space-y-2">
        <p class="text-xs font-semibold text-gray-300">{{ t('settings.db_restore_label') }}</p>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('settings.db_restore_desc') }}</p>
        <div class="flex items-center gap-3">
          <button class="btn text-sm" :disabled="dbRestoring" @click="triggerDbRestore">
            {{ dbRestoring ? t('common.loading') : t('settings.db_restore_btn') }}
          </button>
          <input ref="dbRestoreInput" type="file" accept=".json" class="hidden" @change="handleDbRestore" />
        </div>
        <div v-if="dbRestoreResult && !dbRestoreResult.error" class="text-xs text-green-400 space-y-0.5">
          <p v-for="[key, s] in Object.entries(dbRestoreResult).filter(([k,v]) => typeof v === 'object')" :key="key">
            {{ key }}: {{ s.created }} {{ t('settings.ledger_import_created') }}, {{ s.skipped }} {{ t('settings.ledger_import_skipped') }}<template v-if="s.failed">, {{ s.failed }} {{ t('settings.ledger_import_failed') }}</template>
          </p>
        </div>
        <p v-if="dbRestoreResult?.error" class="text-xs text-red-400">
          {{ t('common.error_prefix') }}{{ dbRestoreResult.error }}
        </p>
      </div>
    </div>

    <!-- Resync / Re-fetch Panel -->
    <div class="card space-y-4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.resync_section') }}</h3>
      <div class="space-y-2">
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('settings.resync_desc') }}</p>
        <button class="btn text-sm" :disabled="resyncing" @click="resyncAllData">
          <span v-if="resyncing">↻ {{ t('common.loading') }}</span>
          <span v-else>↻ {{ t('settings.resync_btn') }}</span>
        </button>
        <p v-if="resyncResult && !resyncResult.error" class="text-xs text-green-400">
          {{ t('settings.resync_queued').replace('{count}', resyncResult.count) }}
        </p>
        <p v-if="resyncResult?.error" class="text-xs text-red-400">
          {{ t('common.error_prefix') }}{{ resyncResult.error }}
        </p>
      </div>
    </div>

    <!-- Import aus Qubic Ledger Panel -->
    <div class="card space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.ledger_section') }}</h3>
      </div>

      <div class="space-y-2">
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('settings.ledger_import_desc') }}</p>
        <a href="https://myledger.qubic.tools/" target="_blank" rel="noopener noreferrer"
           class="text-xs text-qubic-teal hover:underline inline-block">
          ↗ {{ t('settings.ledger_import_link') }}
        </a>
        <div class="flex items-center gap-3 pt-1">
          <button class="btn text-sm" :disabled="ledgerImporting" @click="triggerLedgerImport">
            {{ ledgerImporting ? t('common.loading') : t('settings.ledger_import_btn') }}
          </button>
          <input ref="ledgerFileInput" type="file" accept=".json" class="hidden" @change="handleLedgerFile" />
        </div>
        <p v-if="ledgerImportResult && !ledgerImportResult.error" class="text-xs text-green-400">
          {{ ledgerImportResult.created }} {{ t('settings.ledger_import_created') }},
          {{ ledgerImportResult.skipped }} {{ t('settings.ledger_import_skipped') }}<template v-if="ledgerImportResult.failed">, {{ ledgerImportResult.failed }} {{ t('settings.ledger_import_failed') }}</template>
        </p>
        <p v-if="ledgerImportResult?.error" class="text-xs text-red-400">
          {{ t('common.error_prefix') }}{{ ledgerImportResult.error }}
        </p>
      </div>
    </div>

    <!-- Benachrichtigungen Panel -->
    <div class="card space-y-4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.notify_section') }}</h3>
      <div class="space-y-3">
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('settings.notify_desc') }}</p>

        <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
          <input v-model="notifySettings.enabled" type="checkbox" class="accent-qubic-teal" />
          {{ t('settings.notify_enabled') }}
        </label>

        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('settings.notify_types') }}</label>
          <div class="flex flex-wrap gap-4">
            <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input v-model="notifySettings.notify_tx" type="checkbox" class="accent-qubic-teal" />
              <span class="pill text-xs py-0.5 px-2 bg-amber-500/20 text-amber-400 border-amber-500/30">{{ t('event.badge_tx') }}</span>
              {{ t('event.filter_tx') }}
            </label>
            <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input v-model="notifySettings.notify_event" type="checkbox" class="accent-qubic-teal" />
              <span class="pill text-xs py-0.5 px-2 bg-violet-500/20 text-violet-400 border-violet-500/30">{{ t('event.badge_event') }}</span>
              {{ t('event.filter_event') }}
            </label>
          </div>
          <p class="text-xs text-gray-500 mt-1 leading-snug">{{ t('settings.notify_types_hint') }}</p>
        </div>

        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('settings.notify_url') }}</label>
          <input v-model="notifySettings.webhook_url" type="text" class="input w-full text-sm"
                 placeholder="https://ntfy.sh/mein-topic | https://discord.com/api/webhooks/…" />
        </div>

        <div class="flex flex-wrap items-end gap-3">
          <div>
            <label class="text-xs text-gray-500 block mb-1">{{ t('settings.notify_format') }}</label>
            <div class="flex gap-1">
              <button v-for="f in ['generic', 'discord', 'ntfy']" :key="f"
                      :class="['btn-ghost text-sm py-1.5 px-3', notifySettings.format === f && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                      @click="notifySettings.format = f">
                {{ f === 'generic' ? 'JSON' : f === 'discord' ? 'Discord' : 'ntfy' }}
              </button>
            </div>
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">{{ t('settings.notify_min_amount') }}</label>
            <input v-model.number="notifySettings.min_amount" type="number" min="0" class="input w-40 text-sm" />
          </div>
        </div>

        <div class="flex items-center gap-3 pt-1">
          <button class="btn text-sm" :disabled="notifySaving" @click="saveNotifySettings">
            {{ notifySaving ? t('common.loading') : t('common.save') }}
          </button>
          <button class="btn-ghost text-sm" :disabled="notifyTesting || !notifySettings.webhook_url" @click="testNotification">
            {{ notifyTesting ? t('common.loading') : t('settings.notify_test_btn') }}
          </button>
          <span v-if="notifySaved" class="text-xs text-green-400">✓ {{ t('common.save') }}</span>
          <span v-if="notifyTestResult === true" class="text-xs text-green-400">✓ {{ t('settings.notify_test_ok') }}</span>
          <span v-if="notifyTestResult === false" class="text-xs text-red-400">{{ t('settings.notify_test_failed') }}</span>
        </div>
      </div>
    </div>

  </div>

  <!-- Tab: Bestandsverlauf -->
  <div v-if="activeTab === 'bhistory'" class="space-y-6">

    <!-- Einstellungen -->
    <div class="card space-y-4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.bh_section') }}</h3>
      <div class="space-y-3">
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('settings.bh_desc') }}</p>

        <div class="space-y-2">
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer w-56">
              <input v-model="bhSettings.hourly_enabled" type="checkbox" class="accent-qubic-teal" />
              {{ t('bhistory.series_hourly') }}
            </label>
            <button class="btn-ghost text-xs py-0.5 px-2 text-red-400 border-red-400/40 hover:bg-red-400/10 hover:border-red-400 transition-colors"
                    :disabled="bhResetting === 'hourly'"
                    :title="t('settings.bh_reset_hint')"
                    @click="resetBhSeries('hourly')">
              {{ bhResetting === 'hourly' ? t('common.loading') : '🗑 ' + t('settings.bh_reset_btn') }}
            </button>
          </div>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer w-56">
              <input v-model="bhSettings.daily_enabled" type="checkbox" class="accent-qubic-teal" />
              {{ t('bhistory.series_daily') }} <span class="text-xs text-gray-500">(12:00 UTC)</span>
            </label>
            <button class="btn-ghost text-xs py-0.5 px-2 text-red-400 border-red-400/40 hover:bg-red-400/10 hover:border-red-400 transition-colors"
                    :disabled="bhResetting === 'daily'"
                    :title="t('settings.bh_reset_hint')"
                    @click="resetBhSeries('daily')">
              {{ bhResetting === 'daily' ? t('common.loading') : '🗑 ' + t('settings.bh_reset_btn') }}
            </button>
          </div>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer w-56">
              <input v-model="bhSettings.weekly_enabled" type="checkbox" class="accent-qubic-teal" />
              {{ t('bhistory.series_weekly') }} <span class="text-xs text-gray-500">(Mi/Wed 12:00 UTC)</span>
            </label>
            <button class="btn-ghost text-xs py-0.5 px-2 text-red-400 border-red-400/40 hover:bg-red-400/10 hover:border-red-400 transition-colors"
                    :disabled="bhResetting === 'weekly'"
                    :title="t('settings.bh_reset_hint')"
                    @click="resetBhSeries('weekly')">
              {{ bhResetting === 'weekly' ? t('common.loading') : '🗑 ' + t('settings.bh_reset_btn') }}
            </button>
          </div>
          <p v-if="bhResetResult" class="text-xs text-green-400">
            ✓ {{ t(`bhistory.series_${bhResetResult.kind}`) }}: {{ bhResetResult.deleted }} {{ t('settings.bh_reset_done') }}
          </p>
        </div>
        <p class="text-xs text-gray-500 leading-snug">{{ t('settings.bh_toggle_hint') }}</p>

        <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
          <input v-model="bhSettings.excel_autoexport" type="checkbox" class="accent-qubic-teal" />
          {{ t('settings.bh_autoexport') }}
        </label>
        <p class="text-xs text-gray-500 leading-snug">{{ t('settings.bh_autoexport_hint') }}</p>

        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('settings.bh_retention') }}</label>
          <input v-model.number="bhSettings.hourly_retention_days" type="number" min="0" class="input w-40 text-sm" />
          <p class="text-xs text-gray-500 mt-1 leading-snug">{{ t('settings.bh_retention_hint') }}</p>
        </div>

        <div class="flex items-center gap-3 pt-1">
          <button class="btn text-sm" :disabled="bhSaving" @click="saveBhSettings">
            {{ bhSaving ? t('common.loading') : t('common.save') }}
          </button>
          <button class="btn-ghost text-sm" :disabled="bhRebuilding" @click="rebuildBhExports">
            {{ bhRebuilding ? t('common.loading') : t('settings.bh_rebuild_btn') }}
          </button>
          <span v-if="bhSaved" class="text-xs text-green-400">✓ {{ t('common.save') }}</span>
          <span v-if="bhRebuilt !== null" class="text-xs text-green-400">✓ {{ bhRebuilt }} {{ t('settings.bh_rebuilt') }}</span>
        </div>
      </div>
    </div>

    <!-- Mini-Doku: wird bei jeder Funktionsänderung mitgepflegt -->
    <div class="card space-y-4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('bhdoc.title') }}</h3>
      <p class="text-xs text-gray-400 leading-relaxed">{{ t('bhdoc.intro') }}</p>

      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('bhdoc.capture_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('bhdoc.capture_text') }}</p>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('bhdoc.gaps_text') }}</p>
      </div>

      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('bhdoc.balance_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('bhdoc.balance_text') }}</p>
      </div>

      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('bhdoc.view_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('bhdoc.view_text') }}</p>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('bhdoc.edit_text') }}</p>
      </div>

      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('bhdoc.excel_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('bhdoc.excel_text') }}</p>
        <p class="text-xs text-amber-400/80 leading-relaxed">⚠ {{ t('bhdoc.excel_warning') }}</p>
      </div>

      <div class="space-y-1">
        <h4 class="text-xs font-semibold text-qubic-teal">{{ t('bhdoc.settings_title') }}</h4>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('bhdoc.settings_text') }}</p>
      </div>
    </div>
  </div>

  <!-- Tab: Steuern -->
  <div v-if="activeTab === 'tax'" class="grid grid-cols-1 sm:grid-cols-2 gap-6">
    <p v-if="loadError" class="sm:col-span-2 text-xs text-red-400">{{ t('common.error_prefix') }}{{ loadError }}</p>

    <!-- Tax Panel 1: Land & Methode -->
    <div class="card space-y-4 sm:col-start-1">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('tax.settings_title') }} — {{ t('tax.country') }} &amp; {{ t('tax.method') }}</h3>

      <div class="flex items-start gap-4">
        <span class="text-sm text-gray-400 w-28 shrink-0 pt-1">{{ t('tax.country') }}</span>
        <select v-model="taxSettings.country" class="input flex-1 text-sm">
          <option v-for="(rules, code) in taxCountries" :key="code" :value="code">
            {{ code }} <template v-if="rules.currency"> ({{ rules.currency }})</template>
          </option>
        </select>
      </div>

      <div class="flex items-start gap-4">
        <span class="text-sm text-gray-400 w-28 shrink-0 pt-1">{{ t('tax.method') }}</span>
        <div class="space-y-1.5">
          <div class="flex flex-wrap gap-1">
            <button v-for="[val] in [['FIFO'], ['LIFO'], ['HIFO'], ['AVCO']]"
                    :key="val"
                    :disabled="forcedMethod && val !== forcedMethod"
                    :class="['btn-ghost text-sm py-1.5 px-3', taxSettings.method === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal', forcedMethod && val !== forcedMethod && 'opacity-40 cursor-not-allowed']"
                    @click="taxSettings.method = val">
              {{ val }}
            </button>
          </div>
          <p class="text-xs text-gray-500 leading-snug">
            {{ t(`tax.method_${taxSettings.method.toLowerCase()}_desc`) }}
          </p>
          <p v-if="forcedMethod" class="text-xs text-amber-400 leading-snug">
            {{ t('tax.method_forced', { country: taxSettings.country, method: forcedMethod }) }}
          </p>
        </div>
      </div>

      <div class="rounded-lg border border-qubic-border/40 bg-qubic-bg/50 px-3 py-2.5 text-xs text-gray-500 leading-relaxed">
        {{ t('tax.country_rules') }}
      </div>

      <div class="flex items-center justify-end gap-3 pt-1">
        <span v-if="taxSaved" class="text-xs text-green-400">✓ {{ t('common.save') }}</span>
        <button class="btn px-6" :disabled="taxSaving" @click="saveTaxSettings">
          {{ taxSaving ? t('common.loading') : t('common.save') }}
        </button>
      </div>
    </div>

    <!-- Tax Panel 2: Persönliche Daten -->
    <div class="card space-y-3">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('tax.private_data') }}</h3>

      <div>
        <label class="text-xs text-gray-500 block mb-1">{{ t('tax.name') }}</label>
        <input v-model="taxSettings.name" type="text" class="input w-full text-sm" />
      </div>
      <div>
        <label class="text-xs text-gray-500 block mb-1">{{ t('tax.tax_id') }}</label>
        <input v-model="taxSettings.tax_id" type="text" class="input w-full text-sm" />
      </div>
      <div>
        <label class="text-xs text-gray-500 block mb-1">{{ t('tax.address') }}</label>
        <input v-model="taxSettings.address" type="text" class="input w-full text-sm" />
      </div>

      <div class="flex items-center justify-end gap-3 pt-1">
        <span v-if="taxSaved" class="text-xs text-green-400">✓ {{ t('common.save') }}</span>
        <button class="btn px-6" :disabled="taxSaving" @click="saveTaxSettings">
          {{ taxSaving ? t('common.loading') : t('common.save') }}
        </button>
      </div>
    </div>

    <!-- Tax Panel 3: Geschäftsdaten -->
    <div class="card space-y-3 sm:col-span-2">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('tax.business_data') }}</h3>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('tax.company_name') }}</label>
          <input v-model="taxSettings.company_name" type="text" class="input w-full text-sm" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('tax.company_tax_nr') }}</label>
          <input v-model="taxSettings.company_tax_nr" type="text" class="input w-full text-sm" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('tax.company_vat') }}</label>
          <input v-model="taxSettings.company_vat" type="text" class="input w-full text-sm" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('tax.company_reg') }}</label>
          <input v-model="taxSettings.company_reg" type="text" class="input w-full text-sm" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('tax.company_address') }}</label>
          <input v-model="taxSettings.company_address" type="text" class="input w-full text-sm" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">{{ t('tax.fiscal_year') }}</label>
          <div class="flex gap-1">
            <button :class="['btn-ghost text-sm py-1.5 px-3', taxSettings.fiscal_year === 'jan' && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                    @click="taxSettings.fiscal_year = 'jan'">
              {{ t('tax.fiscal_jan') }}
            </button>
            <button :class="['btn-ghost text-sm py-1.5 px-3', taxSettings.fiscal_year === 'custom' && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                    @click="taxSettings.fiscal_year = 'custom'">
              {{ t('tax.fiscal_custom') }}
            </button>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-end gap-3 pt-1">
        <span v-if="taxSaved" class="text-xs text-green-400">✓ {{ t('common.save') }}</span>
        <button class="btn px-6" :disabled="taxSaving" @click="saveTaxSettings">
          {{ taxSaving ? t('common.loading') : t('common.save') }}
        </button>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import i18next from 'i18next'
import { api } from '../api'
import { ref, computed, onMounted } from 'vue'
import PageHeader from '../components/PageHeader.vue'

const store = useAppStore()
const { t } = useTranslation()

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

onMounted(async () => {
  try {
    const [s, c] = await Promise.all([api.tax.getSettings(), api.tax.getCountries()])
    if (s) Object.assign(taxSettings.value, s)
    if (c) taxCountries.value = c
  } catch (e) {
    console.error(e)
  }
})

async function saveTaxSettings() {
  taxSaving.value = true
  try {
    await api.tax.saveSettings(taxSettings.value)
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

async function exportDbJson() {
  dbExporting.value = true
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
    console.error(err)
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
  <PageHeader :title="t('nav.settings')" :hint="t('page_hint.settings')" />
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
    <!-- Eingangsanimation (nach Darstellung) -->
    <div class="card" style="order:2">
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

    <!-- Darstellung -->
    <div class="card space-y-4" style="order:1">
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


    <!-- Export & Import Panel -->
    <div class="card space-y-4" style="order:3">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.io_title') }}</h3>

      <!-- QubicFlow Backup Export -->
      <div class="space-y-2">
        <p class="text-xs font-semibold text-gray-300">{{ t('settings.db_export_label') }}</p>
        <p class="text-xs text-gray-500 leading-relaxed">{{ t('settings.db_export_desc') }}</p>
        <button class="btn text-sm" :disabled="dbExporting" @click="exportDbJson">
          {{ dbExporting ? t('common.loading') : t('settings.db_export_btn') }}
        </button>
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

    <!-- Import aus Qubic Ledger Panel -->
    <div class="card space-y-4" style="order:4">
      <h3 class="text-sm font-bold uppercase text-gray-400">{{ t('settings.ledger_section') }}</h3>

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

    <!-- Tax Panel 1: Land & Methode -->
    <div class="card space-y-4 sm:col-start-1" style="order:5">
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
                    :class="['btn-ghost text-sm py-1.5 px-3', taxSettings.method === val && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
                    @click="taxSettings.method = val">
              {{ val }}
            </button>
          </div>
          <p class="text-xs text-gray-500 leading-snug">
            {{ t(`tax.method_${taxSettings.method.toLowerCase()}_desc`) }}
          </p>
        </div>
      </div>

      <div class="rounded-lg border border-qubic-border/40 bg-qubic-bg/50 px-3 py-2.5 text-xs text-gray-500 leading-relaxed">
        {{ t('tax.country_rules') }}
      </div>

      <div class="flex justify-end pt-1">
        <button class="btn px-6" :disabled="taxSaving" @click="saveTaxSettings">
          {{ taxSaving ? t('common.loading') : t('common.save') }}
        </button>
      </div>
    </div>

    <!-- Tax Panel 2: Persönliche Daten -->
    <div class="card space-y-3" style="order:6">
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

      <div class="flex justify-end pt-1">
        <button class="btn px-6" :disabled="taxSaving" @click="saveTaxSettings">
          {{ taxSaving ? t('common.loading') : t('common.save') }}
        </button>
      </div>
    </div>

    <!-- Tax Panel 3: Geschäftsdaten -->
    <div class="card space-y-3 sm:col-span-2" style="order:7">
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

      <div class="flex justify-end pt-1">
        <button class="btn px-6" :disabled="taxSaving" @click="saveTaxSettings">
          {{ taxSaving ? t('common.loading') : t('common.save') }}
        </button>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { api, exportUrl } from '../api'
import { useAppStore } from '../stores/app'
import { useTranslation } from 'i18next-vue'
import WalletFilter from '../components/WalletFilter.vue'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'

const { t } = useTranslation()
const store = useAppStore()

const year = ref(new Date().getFullYear())
const mode = ref('private')
const selectedWallets = ref([])
const report = ref(null)
const loadingReport = ref(false)

const modeWallets = computed(() =>
  store.wallets.filter(w => w.wallet_type === mode.value.toUpperCase())
)

watch(mode, () => { selectedWallets.value = [] })

function fmtNum(val, dec = 2) {
  if (val === undefined || val === null) return '—'
  const locale = store.lang === 'de' ? 'de-DE' : 'en-US'
  return Number(val).toLocaleString(locale, { minimumFractionDigits: dec, maximumFractionDigits: dec })
}

function fmtQu(val) {
  if (val === undefined || val === null) return '—'
  const locale = store.lang === 'de' ? 'de-DE' : 'en-US'
  return Number(val).toLocaleString(locale, { maximumFractionDigits: 0 })
}

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    const locale = store.lang === 'de' ? 'de-DE' : 'en-US'
    return new Date(iso).toLocaleDateString(locale)
  } catch { return iso }
}

const ccy = () => report.value?.meta?.currency || report.value?.disposals?.[0]?.currency || 'EUR'

async function generateReport() {
  loadingReport.value = true
  report.value = null
  const ids = selectedWallets.value.length ? selectedWallets.value : modeWallets.value.map(w => w.id)
  try {
    report.value = await api.tax.getReport({
      year: year.value,
      wallet_ids: ids,
      mode: mode.value,
    })
  } catch (e) {
    console.error(e)
  } finally {
    loadingReport.value = false
  }
}

function exportCSV() {
  if (!report.value) return
  const r = report.value
  const currency = ccy()
  const sep = ','
  const lines = []

  lines.push(`QubicFlow Tax Report ${year.value} | Mode: ${mode.value} | Country: ${r.meta?.country || ''} | Method: ${r.meta?.method || ''}`)
  lines.push('')

  // Summary
  const s = r.summary
  lines.push('SUMMARY')
  lines.push(['Field', 'Value'].join(sep))
  lines.push([t('tax.taxable_gains'), `${fmtNum(s.taxable_gains_eur)} ${currency}`].join(sep))
  lines.push([t('tax.tax_free_gains'), `${fmtNum(s.tax_free_gains_eur)} ${currency}`].join(sep))
  lines.push([t('tax.income'), `${fmtNum(s.income_eur)} ${currency}`].join(sep))
  lines.push([t('tax.total_volume'), `${fmtNum(s.total_volume_eur)} ${currency}`].join(sep))
  lines.push([t('tax.transactions'), s.transactions_count].join(sep))
  if (s.threshold) {
    lines.push([t('tax.threshold'), `${fmtNum(s.threshold)} ${currency} — ${s.threshold_exceeded ? t('tax.threshold_exceeded') : t('tax.threshold_not_exceeded')}`].join(sep))
  }
  lines.push('')

  // Disposals
  if (r.disposals?.length) {
    lines.push(t('tax.disposals'))
    lines.push([t('tax.disposal_date'), t('tax.disposal_amount'), t('tax.disposal_cost'), t('tax.disposal_proceeds'), t('tax.disposal_gain'), t('tax.disposal_holding'), t('tax.disposal_free')].join(sep))
    for (const d of r.disposals) {
      const allFree = d.lots?.every(l => l.tax_free)
      const someFree = d.lots?.some(l => l.tax_free)
      const holdDays = d.lots?.[0]?.holding_days ?? '—'
      lines.push([
        d.date ? new Date(d.date).toISOString().slice(0, 10) : '—',
        d.amount_qubic,
        fmtNum(d.cost_basis),
        fmtNum(d.proceeds),
        fmtNum(d.gain),
        holdDays,
        allFree ? t('tax.yes') : someFree ? '~' : t('tax.no'),
      ].join(sep))
    }
    lines.push('')
  }

  // Income
  if (r.income?.length) {
    lines.push(t('tax.income_table'))
    lines.push([t('tax.income_date'), t('tax.income_amount'), t('tax.income_value'), t('tax.income_type')].join(sep))
    for (const i of r.income) {
      lines.push([
        i.date ? new Date(i.date).toISOString().slice(0, 10) : '—',
        i.amount_qubic,
        fmtNum(i.value),
        i.source_type,
      ].join(sep))
    }
    lines.push('')
  }

  // Holdings
  if (r.year_end_holdings?.length) {
    lines.push(t('tax.holdings'))
    lines.push([t('tax.holdings_wallet'), t('tax.holdings_amount'), t('tax.holdings_cost')].join(sep))
    for (const h of r.year_end_holdings) {
      lines.push([h.wallet_id, fmtQu(h.amount_qubic), fmtNum(h.cost_basis_eur)].join(sep))
    }
  }

  const blob = new Blob(['﻿' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `qubicflow-tax-${year.value}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function exportPDF() {
  if (!report.value) return
  const r = report.value
  const s = r.summary
  const currency = ccy()
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })

  // Header
  doc.setFontSize(16)
  doc.setFont('helvetica', 'bold')
  doc.text(`QubicFlow ${t('tax.title')} ${year.value}`, 14, 18)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.setTextColor(100)
  doc.text(`${t('tax.mode')}: ${mode.value === 'private' ? t('tax.mode_private') : t('tax.mode_business')} | ${t('tax.country')}: ${r.meta?.country || ''} | ${t('tax.method')}: ${(r.meta?.method || '').toUpperCase()}`, 14, 25)
  doc.setTextColor(0)

  // Summary table
  doc.setFontSize(11)
  doc.setFont('helvetica', 'bold')
  doc.text(t('tax.summary'), 14, 35)
  doc.setFont('helvetica', 'normal')

  const summaryBody = [
    [t('tax.taxable_gains'), `${fmtNum(s.taxable_gains_eur)} ${currency}`],
    [t('tax.tax_free_gains'), `${fmtNum(s.tax_free_gains_eur)} ${currency}`],
    [t('tax.income'), `${fmtNum(s.income_eur)} ${currency}`],
    [t('tax.total_volume'), `${fmtNum(s.total_volume_eur)} ${currency}`],
    [t('tax.transactions'), String(s.transactions_count)],
  ]
  if (s.threshold !== null && s.threshold !== undefined) {
    summaryBody.push([
      `${t('tax.threshold')} (${s.threshold_type || ''})`,
      `${fmtNum(s.threshold)} ${currency} — ${s.threshold_exceeded ? t('tax.threshold_exceeded') : t('tax.threshold_not_exceeded')}`,
    ])
  }

  autoTable(doc, {
    startY: 39,
    head: [['', '']],
    body: summaryBody,
    styles: { fontSize: 9 },
    headStyles: { fillColor: [0, 178, 181], textColor: 255 },
    columnStyles: { 1: { halign: 'right', fontStyle: 'bold' } },
    showHead: false,
  })

  // Disposals
  if (r.disposals?.length) {
    const startY = (doc.lastAutoTable?.finalY || 39) + 8
    doc.setFontSize(11)
    doc.setFont('helvetica', 'bold')
    doc.text(t('tax.disposals'), 14, startY)
    doc.setFont('helvetica', 'normal')
    autoTable(doc, {
      startY: startY + 4,
      head: [[t('tax.disposal_date'), t('tax.disposal_amount'), t('tax.disposal_cost'), t('tax.disposal_proceeds'), t('tax.disposal_gain'), t('tax.disposal_holding'), t('tax.disposal_free')]],
      body: r.disposals.map(d => {
        const allFree = d.lots?.every(l => l.tax_free)
        const someFree = d.lots?.some(l => l.tax_free)
        const holdDays = d.lots?.find(l => l.holding_days !== null)?.holding_days ?? '—'
        return [
          d.date ? new Date(d.date).toISOString().slice(0, 10) : '—',
          fmtQu(d.amount_qubic),
          `${fmtNum(d.cost_basis)} ${currency}`,
          `${fmtNum(d.proceeds)} ${currency}`,
          `${fmtNum(d.gain)} ${currency}`,
          holdDays,
          allFree ? t('tax.yes') : someFree ? '~' : t('tax.no'),
        ]
      }),
      styles: { fontSize: 8 },
      headStyles: { fillColor: [0, 178, 181], textColor: 255 },
    })
  }

  // Income
  if (r.income?.length) {
    const startY = (doc.lastAutoTable?.finalY || 39) + 8
    doc.setFontSize(11)
    doc.setFont('helvetica', 'bold')
    doc.text(t('tax.income_table'), 14, startY)
    doc.setFont('helvetica', 'normal')
    autoTable(doc, {
      startY: startY + 4,
      head: [[t('tax.income_date'), t('tax.income_amount'), t('tax.income_value'), t('tax.income_type')]],
      body: r.income.map(i => [
        i.date ? new Date(i.date).toISOString().slice(0, 10) : '—',
        fmtQu(i.amount_qubic),
        `${fmtNum(i.value)} ${currency}`,
        i.source_type === 'EVENT' ? t('tax.income_reward') : i.source_type,
      ]),
      styles: { fontSize: 8 },
      headStyles: { fillColor: [0, 178, 181], textColor: 255 },
    })
  }

  // Year-end holdings
  if (r.year_end_holdings?.length) {
    const startY = (doc.lastAutoTable?.finalY || 39) + 8
    doc.setFontSize(11)
    doc.setFont('helvetica', 'bold')
    doc.text(t('tax.holdings'), 14, startY)
    doc.setFont('helvetica', 'normal')
    autoTable(doc, {
      startY: startY + 4,
      head: [[t('tax.holdings_wallet'), t('tax.holdings_amount'), t('tax.holdings_cost')]],
      body: r.year_end_holdings.map(h => [
        store.hideAddresses ? '••••••••••••' : (store.wallets.find(w => w.id === h.wallet_id)?.label || h.wallet_id.slice(0, 12) + '…'),
        fmtQu(h.amount_qubic),
        `${fmtNum(h.cost_basis_eur)} ${currency}`,
      ]),
      styles: { fontSize: 8 },
      headStyles: { fillColor: [0, 178, 181], textColor: 255 },
    })
  }

  // Disclaimer
  const disclaimerY = (doc.lastAutoTable?.finalY || 200) + 12
  doc.setFontSize(7)
  doc.setTextColor(140)
  doc.text(doc.splitTextToSize(t('tax.disclaimer'), 182), 14, disclaimerY)

  doc.save(`qubicflow-tax-${year.value}.pdf`)
}
</script>

<template>
  <div class="space-y-4">

    <!-- Controls -->
    <div class="card space-y-4">
      <h2 class="text-sm font-bold uppercase text-gray-400">{{ t('tax.title') }}</h2>

      <div class="flex flex-wrap items-center gap-4">
        <!-- Year -->
        <div class="flex items-center gap-2">
          <span class="text-sm text-gray-400 whitespace-nowrap">{{ t('tax.year') }}</span>
          <input v-model.number="year" type="number" class="input w-24 text-center" min="2024" :max="new Date().getFullYear()" />
        </div>

        <!-- Mode -->
        <div class="flex items-center gap-2">
          <span class="text-sm text-gray-400 whitespace-nowrap">{{ t('tax.mode') }}</span>
          <div class="flex gap-1">
            <button
              :class="['btn-ghost text-sm py-1.5 px-3', mode === 'private' && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
              @click="mode = 'private'">
              {{ t('tax.mode_private') }}
            </button>
            <button
              :class="['btn-ghost text-sm py-1.5 px-3', mode === 'business' && 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal']"
              @click="mode = 'business'">
              {{ t('tax.mode_business') }}
            </button>
          </div>
        </div>

        <button class="btn ml-auto" :disabled="loadingReport" @click="generateReport">
          {{ t('tax.generate') }}
        </button>
      </div>
    </div>

    <!-- Wallet Filter -->
    <WalletFilter v-model="selectedWallets" :wallets="modeWallets" />


    <!-- Loading -->
    <div v-if="loadingReport" class="card flex items-center justify-center py-12">
      <div class="flex items-center gap-3 text-sm text-gray-400">
        <div class="w-5 h-5 rounded-full border-2 border-qubic-border border-t-qubic-teal animate-spin" />
        {{ t('tax.loading') }}
      </div>
    </div>

    <!-- Report -->
    <template v-if="report && !loadingReport">

      <!-- Data warning -->
      <div class="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-xs text-amber-300">
        {{ t('tax.data_warning') }}
      </div>

      <!-- Export buttons -->
      <div class="flex flex-wrap gap-2 justify-end">
        <a :href="exportUrl('cointracking', year)" class="btn-ghost text-sm py-1.5 px-4">{{ t('export.cointracking') }}</a>
        <a :href="exportUrl('steuerberater', year)" class="btn-ghost text-sm py-1.5 px-4">{{ t('export.steuerberater') }}</a>
        <button class="btn-ghost text-sm py-1.5 px-4" @click="exportCSV">{{ t('tax.export_csv') }}</button>
        <button class="btn text-sm py-1.5 px-4" @click="exportPDF">{{ t('tax.export_pdf') }}</button>
      </div>

      <!-- Summary -->
      <div class="card">
        <h3 class="text-sm font-bold uppercase text-gray-400 mb-4">{{ t('tax.summary') }}</h3>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div class="rounded-lg border border-qubic-border bg-qubic-bg/50 px-4 py-3">
            <div class="text-xs text-gray-500 mb-1">{{ t('tax.taxable_gains') }}</div>
            <div :class="['text-base font-mono font-semibold', (report.summary.taxable_gains_eur || 0) >= 0 ? 'text-green-400' : 'text-red-400']">
              {{ fmtNum(report.summary.taxable_gains_eur) }} {{ ccy() }}
            </div>
          </div>
          <div class="rounded-lg border border-qubic-border bg-qubic-bg/50 px-4 py-3">
            <div class="text-xs text-gray-500 mb-1">{{ t('tax.tax_free_gains') }}</div>
            <div class="text-base font-mono font-semibold text-qubic-teal">
              {{ fmtNum(report.summary.tax_free_gains_eur) }} {{ ccy() }}
            </div>
          </div>
          <div class="rounded-lg border border-qubic-border bg-qubic-bg/50 px-4 py-3">
            <div class="text-xs text-gray-500 mb-1">{{ t('tax.income') }}</div>
            <div class="text-base font-mono font-semibold text-qubic-teal">
              {{ fmtNum(report.summary.income_eur) }} {{ ccy() }}
            </div>
          </div>
          <div class="rounded-lg border border-qubic-border bg-qubic-bg/50 px-4 py-3">
            <div class="text-xs text-gray-500 mb-1">{{ t('tax.total_volume') }}</div>
            <div class="text-base font-mono font-semibold text-gray-300">
              {{ fmtNum(report.summary.total_volume_eur) }} {{ ccy() }}
            </div>
          </div>
          <div class="rounded-lg border border-qubic-border bg-qubic-bg/50 px-4 py-3">
            <div class="text-xs text-gray-500 mb-1">{{ t('tax.transactions') }}</div>
            <div class="text-base font-mono font-semibold text-gray-300">
              {{ report.summary.transactions_count }}
            </div>
          </div>
          <div v-if="report.summary.threshold !== null && report.summary.threshold !== undefined"
               :class="['rounded-lg border px-4 py-3', report.summary.threshold_exceeded ? 'border-red-500/50 bg-red-500/10' : 'border-green-500/40 bg-green-500/10']">
            <div class="text-xs text-gray-500 mb-1">{{ t('tax.threshold') }}</div>
            <div :class="['text-sm font-semibold', report.summary.threshold_exceeded ? 'text-red-400' : 'text-green-400']">
              {{ fmtNum(report.summary.threshold) }} {{ ccy() }}
            </div>
            <div :class="['text-xs mt-0.5', report.summary.threshold_exceeded ? 'text-red-400' : 'text-green-400']">
              {{ report.summary.threshold_exceeded ? t('tax.threshold_exceeded') : t('tax.threshold_not_exceeded') }}
            </div>
          </div>
        </div>
      </div>

      <!-- No data -->
      <div v-if="!report.disposals?.length && !report.income?.length" class="card text-sm text-gray-400 text-center py-6">
        {{ t('tax.no_data') }}
      </div>

      <!-- Disposals -->
      <div v-if="report.disposals?.length" class="card">
        <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('tax.disposals') }}</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-qubic-border text-gray-500 uppercase">
                <th class="text-left py-2 pr-3">{{ t('tax.disposal_date') }}</th>
                <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.disposal_amount') }}</th>
                <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.disposal_cost') }}</th>
                <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.disposal_proceeds') }}</th>
                <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.disposal_gain') }}</th>
                <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.disposal_holding') }}</th>
                <th class="text-center py-2">{{ t('tax.disposal_free') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(d, i) in report.disposals" :key="i"
                  class="border-b border-qubic-border/30 hover:bg-qubic-teal/5 transition-colors">
                <td class="py-2 pr-3 text-gray-300 whitespace-nowrap">{{ fmtDate(d.date) }}</td>
                <td class="py-2 pr-3 text-right font-mono whitespace-nowrap">{{ fmtQu(d.amount_qubic) }}</td>
                <td class="py-2 pr-3 text-right font-mono whitespace-nowrap">{{ fmtNum(d.cost_basis) }}</td>
                <td class="py-2 pr-3 text-right font-mono whitespace-nowrap">{{ fmtNum(d.proceeds) }}</td>
                <td :class="['py-2 pr-3 text-right font-mono whitespace-nowrap font-semibold', d.gain >= 0 ? 'text-green-400' : 'text-red-400']">
                  {{ fmtNum(d.gain) }}
                </td>
                <td class="py-2 pr-3 text-right text-gray-400 whitespace-nowrap">
                  {{ d.lots?.find(l => l.holding_days !== null)?.holding_days ?? '—' }}
                </td>
                <td class="py-2 text-center">
                  <span v-if="d.lots?.every(l => l.tax_free)" class="text-green-400">✓</span>
                  <span v-else-if="d.lots?.some(l => l.tax_free)" class="text-amber-400">~</span>
                  <span v-else class="text-gray-600">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Income / Rewards -->
      <div v-if="report.income?.length" class="card">
        <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('tax.income_table') }}</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="border-b border-qubic-border text-gray-500 uppercase">
                <th class="text-left py-2 pr-3">{{ t('tax.income_date') }}</th>
                <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.income_amount') }}</th>
                <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.income_value') }}</th>
                <th class="text-left py-2">{{ t('tax.income_type') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, i) in report.income" :key="i"
                  class="border-b border-qubic-border/30 hover:bg-qubic-teal/5 transition-colors">
                <td class="py-2 pr-3 text-gray-300 whitespace-nowrap">{{ fmtDate(item.date) }}</td>
                <td class="py-2 pr-3 text-right font-mono whitespace-nowrap">{{ fmtQu(item.amount_qubic) }}</td>
                <td class="py-2 pr-3 text-right font-mono whitespace-nowrap text-qubic-teal">{{ fmtNum(item.value) }} {{ ccy() }}</td>
                <td class="py-2 text-gray-400">{{ item.source_type === 'EVENT' ? t('tax.income_reward') : item.source_type }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Year-end Holdings -->
      <div v-if="report.year_end_holdings?.length" class="card">
        <h3 class="text-sm font-bold uppercase text-gray-400 mb-3">{{ t('tax.holdings') }}</h3>
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-qubic-border text-gray-500 uppercase">
              <th class="text-left py-2 pr-3">{{ t('tax.holdings_wallet') }}</th>
              <th class="text-right py-2 pr-3 whitespace-nowrap">{{ t('tax.holdings_amount') }}</th>
              <th class="text-right py-2 whitespace-nowrap">{{ t('tax.holdings_cost') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(h, i) in report.year_end_holdings" :key="i"
                class="border-b border-qubic-border/30">
              <td class="py-2 pr-3 text-gray-300 font-mono text-xs">
                {{ store.hideAddresses ? '••••••••••••' : (store.wallets.find(w => w.id === h.wallet_id)?.label || h.wallet_id.slice(0, 16) + '…') }}
              </td>
              <td class="py-2 pr-3 text-right font-mono">{{ fmtQu(h.amount_qubic) }}</td>
              <td class="py-2 text-right font-mono">{{ fmtNum(h.cost_basis_eur) }} {{ ccy() }}</td>
            </tr>
          </tbody>
        </table>
      </div>

    </template>

    <!-- Disclaimer -->
    <div class="rounded-lg border border-qubic-border/40 bg-qubic-bg/30 px-4 py-3 text-xs text-gray-500 leading-relaxed">
      {{ t('tax.disclaimer') }}
    </div>

  </div>
</template>

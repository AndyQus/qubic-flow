<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { useTranslation } from 'i18next-vue'

const { t } = useTranslation()

const allLabels = ref([])
const search = ref('')
const categoryFilter = ref('all')
const loading = ref(true)

onMounted(async () => {
  try {
    allLabels.value = await api.labels.list()
  } finally {
    loading.value = false
  }
})

const categories = computed(() => {
  const cats = new Set(allLabels.value.map(l => l.category).filter(Boolean))
  return ['all', ...cats]
})

const filtered = computed(() => {
  let list = allLabels.value
  if (categoryFilter.value !== 'all') {
    list = list.filter(l => l.category === categoryFilter.value)
  }
  const q = search.value.trim().toLowerCase()
  if (q) {
    list = list.filter(l =>
      (l.name || '').toLowerCase().includes(q) ||
      (l.label || '').toLowerCase().includes(q) ||
      (l.address || '').toLowerCase().includes(q)
    )
  }
  return list.slice().sort((a, b) => {
    const na = a.label || a.name || ''
    const nb = b.label || b.name || ''
    return na.localeCompare(nb)
  })
})

const stats = computed(() => {
  const total = allLabels.value.length
  const byCategory = {}
  for (const l of allLabels.value) {
    const c = l.category || 'standard'
    byCategory[c] = (byCategory[c] || 0) + 1
  }
  return { total, byCategory }
})

function displayName(l) {
  return l.label || l.name || '—'
}

function truncate(addr) {
  if (!addr) return '—'
  return addr.slice(0, 8) + '…' + addr.slice(-8)
}

async function copyAddress(addr) {
  await navigator.clipboard.writeText(addr)
}

function explorerUrl(addr) {
  return `https://explorer.qubic.org/network/address/${addr}`
}

function categoryLabel(cat) {
  const key = `assets.category_${cat}`
  const translated = t(key)
  return translated !== key ? translated : (cat || '—')
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header & Stats -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex gap-4 text-sm text-gray-400">
        <span>{{ t('assets.total') }}: <span class="font-medium">{{ stats.total }}</span></span>
        <span v-for="(count, cat) in stats.byCategory" :key="cat">
          {{ categoryLabel(cat) }}: <span class="font-medium">{{ count }}</span>
        </span>
      </div>
    </div>

    <!-- Filter & Search -->
    <div class="flex flex-wrap gap-2 items-center">
      <button
        v-for="cat in categories"
        :key="cat"
        :class="[
          'btn-ghost text-sm',
          cat === 'all'            && categoryFilter === cat ? 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal' : '',
          cat === 'smart_contract' && categoryFilter === cat ? 'bg-purple-500/20 border-purple-500 text-purple-400'  : '',
          cat === 'exchange'       && categoryFilter === cat ? 'bg-orange-500/20 border-orange-500 text-orange-400'  : '',
          cat === 'liquid_staking' && categoryFilter === cat ? 'bg-blue-500/20 border-blue-500 text-blue-400'        : '',
          cat === 'standard'       && categoryFilter === cat ? 'bg-qubic-teal/20 border-qubic-teal text-qubic-teal' : '',
        ]"
        @click="categoryFilter = cat"
      >
        {{ cat === 'all' ? t('filter.all') : categoryLabel(cat) }}
      </button>
      <input
        v-model="search"
        :placeholder="t('assets.search')"
        class="input ml-auto w-64 text-sm"
      />
    </div>

    <!-- Table -->
    <div class="card overflow-hidden p-0">
      <div v-if="loading" class="p-8 text-center text-gray-500">{{ t('common.loading') }}</div>
      <table v-else class="w-full text-xs">
        <thead class="border-b border-qubic-border text-gray-400 text-xs uppercase">
          <tr>
            <th class="text-left p-3">{{ t('assets.name') }}</th>
            <th class="text-left p-3">{{ t('assets.ticker') }}</th>
            <th class="text-left p-3">{{ t('assets.address') }}</th>
            <th class="text-left p-3">{{ t('assets.category') }}</th>
            <th class="text-center p-3">{{ t('assets.decimals') }}</th>
            <th class="text-left p-3">{{ t('assets.website') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!filtered.length">
            <td colspan="6" class="text-center p-8 text-gray-500">{{ t('assets.none') }}</td>
          </tr>
          <tr
            v-for="l in filtered"
            :key="l.address"
            class="border-b border-qubic-border/50 hover:bg-qubic-teal/5 transition-colors"
          >
            <!-- Name / Label -->
            <td class="p-3">
              {{ displayName(l) }}
            </td>

            <!-- Ticker -->
            <td class="p-3">
              <span v-if="l.name" class="pill text-xs">{{ l.name }}</span>
              <span v-else class="text-gray-500">—</span>
            </td>

            <!-- Address with copy + explorer link -->
            <td class="p-3">
              <div class="flex items-center gap-2 font-mono text-xs text-gray-400">
                <span :title="l.address">{{ truncate(l.address) }}</span>
                <button
                  class="hover:text-qubic-teal transition-colors"
                  :title="t('assets.copy')"
                  @click="copyAddress(l.address)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                  </svg>
                </button>
                <a
                  :href="explorerUrl(l.address)"
                  target="_blank"
                  rel="noopener"
                  class="hover:text-qubic-teal transition-colors"
                  :title="t('assets.explorer')"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                  </svg>
                </a>
              </div>
            </td>

            <!-- Category -->
            <td class="p-3">
              <span
                v-if="l.category"
                :class="[
                  'pill text-xs',
                  l.category === 'smart_contract' ? 'bg-purple-500/20 text-purple-400 border-purple-500/30' :
                  l.category === 'exchange'        ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' :
                  l.category === 'liquid_staking'  ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                                                     'bg-qubic-teal/20 text-qubic-teal border-qubic-teal/30'
                ]"
              >
                {{ categoryLabel(l.category) }}
              </span>
              <span v-else class="text-gray-500">—</span>
            </td>

            <!-- Decimal places -->
            <td class="p-3 text-center text-gray-400">
              {{ l.decimal_places ?? '—' }}
            </td>

            <!-- Website -->
            <td class="p-3">
              <a
                v-if="l.website"
                :href="l.website.startsWith('http') ? l.website : 'https://' + l.website"
                target="_blank"
                rel="noopener"
                class="text-qubic-teal hover:text-qubic-cyan text-xs truncate max-w-[160px] inline-block"
              >
                {{ l.website }}
              </a>
              <span v-else class="text-gray-500">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

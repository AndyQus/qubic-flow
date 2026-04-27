<script setup>
import { useTranslation } from 'i18next-vue'
import logoMark from '../assets/logo-mark.svg'

const { t } = useTranslation()
const APP_VERSION = 'v0.1.9 (BETA)'
const year = new Date().getFullYear()
</script>

<style scoped>
.footer-fixed,
.footer-fixed * {
  font-size: 12px !important;
}
</style>

<template>
  <!-- Disclaimer Banner -->
  <div class="footer-fixed footer-disclaimer border-t border-amber-800/40 bg-amber-950/30 px-4 sm:px-6 lg:px-8 py-2.5">
    <div class="w-full flex items-start justify-center text-amber-200/75 text-center" style="gap:6px">
      <svg xmlns="http://www.w3.org/2000/svg" class="text-amber-400 shrink-0" style="width:16px;height:16px;margin-top:1px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
      <p>
        <strong class="text-amber-300 font-semibold">{{ t('footer.disclaimer_label') }}:</strong>
        {{ t('footer.disclaimer_pre') }}
        <a href="https://rpc.qubic.org" target="_blank" rel="noopener noreferrer" class="underline hover:text-amber-100 transition-colors">rpc.qubic.org</a>
        {{ t('footer.disclaimer_post') }}
      </p>
    </div>
  </div>

  <!-- Footer -->
  <footer class="footer-fixed footer-bar border-t border-qubic-border bg-qubic-card/40 backdrop-blur-glass">
    <div class="w-full px-4 sm:px-6 lg:px-8 py-3 relative flex items-center justify-between text-gray-400">

      <!-- Left: logo + copyright -->
      <div class="flex items-center gap-2">
        <img :src="logoMark" alt="Qubic" class="h-4 w-auto opacity-70" />
        <span>© {{ year }} Qubic – Sponsored by AndyQus</span>
      </div>

      <!-- Center: links (absolute so they are truly centered) -->
      <div class="absolute inset-x-0 flex items-center justify-center gap-2 pointer-events-none">
        <div class="flex items-center gap-2 pointer-events-auto">
          <a href="https://qubic.org" target="_blank" rel="noopener noreferrer" class="underline hover:text-qubic-teal transition-colors">Qubic.org</a>
          <span class="text-gray-600">·</span>
          <a href="https://qubic.org/terms-of-service" target="_blank" rel="noopener noreferrer" class="underline hover:text-qubic-teal transition-colors">{{ t('footer.terms') }}</a>
          <span class="text-gray-600">·</span>
          <a href="https://qubic.org/privacy-policy" target="_blank" rel="noopener noreferrer" class="underline hover:text-qubic-teal transition-colors">{{ t('footer.privacy') }}</a>
        </div>
      </div>

      <!-- Right: version -->
      <div>{{ APP_VERSION }}</div>

    </div>
  </footer>
</template>

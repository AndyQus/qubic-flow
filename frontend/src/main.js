import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import i18next from 'i18next'
import I18NextVue from 'i18next-vue'
import { MotionPlugin } from '@vueuse/motion'
import { de } from './i18n/de'
import { en } from './i18n/en'
import App from './App.vue'
import './style.css'

i18next.init({
  lng: localStorage.getItem('lang') || 'de',
  fallbackLng: 'en',
  resources: { de: { translation: de }, en: { translation: en } },
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(I18NextVue, { i18next })
app.use(MotionPlugin)
app.mount('#app')

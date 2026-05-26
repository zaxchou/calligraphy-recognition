import { createI18n } from 'vue-i18n'
import zh from './zh'
import en from './en'

const savedLang = localStorage.getItem('lang') || 'zh'

const i18n = createI18n({
  legacy: false,
  locale: savedLang,
  fallbackLocale: 'zh',
  messages: { zh, en },
  silentTranslationWarn: true,
  silentFallbackWarn: true,
})

export function switchLang(lang) {
  i18n.global.locale.value = lang
  localStorage.setItem('lang', lang)
}

export default i18n

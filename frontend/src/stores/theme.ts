import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', () => {
  // State
  const mode = ref<ThemeMode>('dark')
  const isDark = ref(true)

  // Initialize from localStorage or system preference
  function initialize() {
    const savedTheme = localStorage.getItem('theme') as ThemeMode | null

    if (savedTheme) {
      mode.value = savedTheme
    } else {
      mode.value = 'system'
    }

    applyTheme()
  }

  // Apply theme to document
  function applyTheme() {
    let dark = false

    if (mode.value === 'dark') {
      dark = true
    } else if (mode.value === 'light') {
      dark = false
    } else {
      // System preference
      dark = window.matchMedia('(prefers-color-scheme: dark)').matches
    }

    isDark.value = dark

    if (dark) {
      document.documentElement.classList.add('dark')
      document.documentElement.classList.remove('light')
    } else {
      document.documentElement.classList.add('light')
      document.documentElement.classList.remove('dark')
    }
  }

  // Set theme mode
  function setMode(newMode: ThemeMode) {
    mode.value = newMode
    localStorage.setItem('theme', newMode)
    applyTheme()
  }

  // Toggle between light and dark
  function toggle() {
    if (mode.value === 'dark' || (mode.value === 'system' && isDark.value)) {
      setMode('light')
    } else {
      setMode('dark')
    }
  }

  // Listen for system preference changes
  function setupSystemListener() {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', () => {
      if (mode.value === 'system') {
        applyTheme()
      }
    })
  }

  return {
    mode,
    isDark,
    initialize,
    setMode,
    toggle,
    setupSystemListener,
  }
})

import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

export interface ResearchIntegritySettings {
  verificationEnabled: boolean
  strictMode: boolean
  sourceAttributionRequired: boolean
  confidenceThresholdPass: number
  confidenceThresholdFlag: number
}

export interface LLMSettings {
  // Active provider: "ollama", "openai", or "gemini"
  provider: string
  // Ollama settings
  ollamaHost: string
  ollamaModel: string
  // OpenAI settings
  openaiModel: string
  // Gemini settings
  geminiModel: string
}

export interface AppSettings {
  researchIntegrity: ResearchIntegritySettings
  llm: LLMSettings
}

const STORAGE_KEY = 'smart-hes-settings'

const DEFAULT_SETTINGS: AppSettings = {
  researchIntegrity: {
    verificationEnabled: true,
    strictMode: false,
    sourceAttributionRequired: true,
    confidenceThresholdPass: 0.85,
    confidenceThresholdFlag: 0.70,
  },
  llm: {
    provider: 'ollama',
    ollamaHost: 'http://localhost:11434',
    ollamaModel: 'llama3.1:8b-instruct-q4_K_M',
    openaiModel: 'gpt-4o',
    geminiModel: 'gemini-2.0-flash',
  },
}

export const useSettingsStore = defineStore('settings', () => {
  // State
  const researchIntegrity = ref<ResearchIntegritySettings>({ ...DEFAULT_SETTINGS.researchIntegrity })
  const llm = ref<LLMSettings>({ ...DEFAULT_SETTINGS.llm })
  const isLoaded = ref(false)

  // Computed - flat accessors for convenience
  const verificationEnabled = computed(() => researchIntegrity.value.verificationEnabled)
  const strictMode = computed(() => researchIntegrity.value.strictMode)
  const sourceAttributionRequired = computed(() => researchIntegrity.value.sourceAttributionRequired)
  const confidenceThresholdPass = computed(() => researchIntegrity.value.confidenceThresholdPass)
  const confidenceThresholdFlag = computed(() => researchIntegrity.value.confidenceThresholdFlag)
  const llmProvider = computed(() => llm.value.provider)
  const ollamaHost = computed(() => llm.value.ollamaHost)
  const ollamaModel = computed(() => llm.value.ollamaModel)
  const openaiModel = computed(() => llm.value.openaiModel)
  const geminiModel = computed(() => llm.value.geminiModel)

  // Computed - current active model based on provider
  const activeModel = computed(() => {
    if (llm.value.provider === 'openai') {
      return llm.value.openaiModel
    } else if (llm.value.provider === 'gemini') {
      return llm.value.geminiModel
    }
    return llm.value.ollamaModel
  })

  // Computed - status summary for dashboard
  const integrityStatus = computed(() => {
    if (researchIntegrity.value.strictMode) return 'strict'
    if (researchIntegrity.value.verificationEnabled) return 'active'
    return 'disabled'
  })

  const integrityStatusColor = computed(() => {
    switch (integrityStatus.value) {
      case 'strict': return 'var(--status-warning)'
      case 'active': return 'var(--status-success)'
      default: return 'var(--status-danger)'
    }
  })

  // Initialize from localStorage
  function initialize() {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as Partial<AppSettings>

        // Merge with defaults to handle missing properties from older versions
        if (parsed.researchIntegrity) {
          researchIntegrity.value = {
            ...DEFAULT_SETTINGS.researchIntegrity,
            ...parsed.researchIntegrity,
          }
        }
        if (parsed.llm) {
          llm.value = {
            ...DEFAULT_SETTINGS.llm,
            ...parsed.llm,
          }
        }
      } catch (e) {
        console.error('Failed to parse settings from localStorage:', e)
        resetToDefaults()
      }
    }
    isLoaded.value = true
  }

  // Save to localStorage
  function save() {
    const settings: AppSettings = {
      researchIntegrity: { ...researchIntegrity.value },
      llm: { ...llm.value },
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  }

  // Reset to defaults
  function resetToDefaults() {
    researchIntegrity.value = { ...DEFAULT_SETTINGS.researchIntegrity }
    llm.value = { ...DEFAULT_SETTINGS.llm }
    save()
  }

  // Update research integrity settings
  function updateResearchIntegrity(updates: Partial<ResearchIntegritySettings>) {
    researchIntegrity.value = {
      ...researchIntegrity.value,
      ...updates,
    }
    save()
  }

  // Update LLM settings
  function updateLLM(updates: Partial<LLMSettings>) {
    llm.value = {
      ...llm.value,
      ...updates,
    }
    save()
  }

  // Watch for changes and auto-save (reactive persistence)
  watch(
    [researchIntegrity, llm],
    () => {
      if (isLoaded.value) {
        save()
      }
    },
    { deep: true }
  )

  return {
    // State
    researchIntegrity,
    llm,
    isLoaded,

    // Computed - flat accessors
    verificationEnabled,
    strictMode,
    sourceAttributionRequired,
    confidenceThresholdPass,
    confidenceThresholdFlag,
    llmProvider,
    ollamaHost,
    ollamaModel,
    openaiModel,
    geminiModel,
    activeModel,

    // Computed - status
    integrityStatus,
    integrityStatusColor,

    // Actions
    initialize,
    save,
    resetToDefaults,
    updateResearchIntegrity,
    updateLLM,
  }
})
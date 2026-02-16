import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  modeApi,
  type InteractionMode as ApiInteractionMode,
  type ExpertConsultationResponse,
  type PreloadedScenario,
  type ModeStatusResponse,
} from '@/services/modeApi'

export type InteractionMode = 'llm' | 'no-llm'

export interface ExpertConsultation {
  id: string
  question: string
  context: string
  timestamp: Date
  status: 'pending' | 'accepted' | 'rejected'
  response?: string
  sources?: string[]
  confidence?: string
  confidenceScore?: number
  verificationNotes?: string[]
}

export interface ScenarioExecutionResult {
  execution_id: string
  scenario_id: string
  scenario_name: string
  status: string
  home_id?: string
  simulation_id?: string
  results?: Record<string, unknown>
  timestamp: string
}

export const useModeStore = defineStore('mode', () => {
  // State
  const mode = ref<InteractionMode>('llm')
  const consultations = ref<ExpertConsultation[]>([])
  const showConsultationDialog = ref(false)
  const currentConsultation = ref<ExpertConsultation | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const llmAvailable = ref(true)
  const scenarios = ref<PreloadedScenario[]>([])
  const lastExecutedScenario = ref<ScenarioExecutionResult | null>(null)

  // Computed
  const isLLMMode = computed(() => mode.value === 'llm')
  const isNoLLMMode = computed(() => mode.value === 'no-llm')
  const pendingConsultations = computed(() =>
    consultations.value.filter(c => c.status === 'pending')
  )
  const hasPendingConsultations = computed(() => pendingConsultations.value.length > 0)
  const acceptedConsultations = computed(() =>
    consultations.value.filter(c => c.status === 'accepted')
  )
  const rejectedConsultations = computed(() =>
    consultations.value.filter(c => c.status === 'rejected')
  )

  // Initialize from backend and session storage
  async function initialize() {
    // First load from session storage for immediate UI
    const savedMode = sessionStorage.getItem('interaction-mode') as InteractionMode | null
    if (savedMode && (savedMode === 'llm' || savedMode === 'no-llm')) {
      mode.value = savedMode
      modeApi.setCurrentModeLocal(savedMode)
    }

    // Load consultations from session storage
    const savedConsultations = sessionStorage.getItem('consultations')
    if (savedConsultations) {
      try {
        const parsed = JSON.parse(savedConsultations)
        consultations.value = parsed.map((c: ExpertConsultation) => ({
          ...c,
          timestamp: new Date(c.timestamp)
        }))
      } catch {
        consultations.value = []
      }
    }

    // Then sync with backend (non-blocking)
    try {
      const status = await modeApi.getStatus()
      mode.value = status.mode
      llmAvailable.value = status.llm_available
      modeApi.setCurrentModeLocal(status.mode)

      // Load scenarios
      scenarios.value = await modeApi.listScenarios()

      // Sync consultations from backend
      const backendConsultations = await modeApi.listConsultations()
      if (backendConsultations.length > 0) {
        consultations.value = backendConsultations.map(c => ({
          id: c.id,
          question: c.question,
          context: c.context,
          timestamp: new Date(c.timestamp),
          status: c.status,
          response: c.response,
          sources: c.sources,
          confidence: c.confidence,
          confidenceScore: c.confidence_score,
          verificationNotes: c.verification_notes,
        }))
        persistConsultations()
      }
    } catch (e) {
      console.warn('Failed to sync with backend, using local state:', e)
    }
  }

  // Set mode and persist to backend
  async function setMode(newMode: InteractionMode) {
    const previousMode = mode.value
    mode.value = newMode
    sessionStorage.setItem('interaction-mode', newMode)
    modeApi.setCurrentModeLocal(newMode)

    try {
      await modeApi.setMode(newMode)
    } catch (e) {
      console.error('Failed to sync mode to backend:', e)
      // Keep local change even if backend fails
    }
  }

  // Toggle between modes
  function toggleMode() {
    setMode(mode.value === 'llm' ? 'no-llm' : 'llm')
  }

  // Create a new expert consultation request via API
  async function requestConsultation(question: string, context: string = ''): Promise<ExpertConsultation> {
    isLoading.value = true
    error.value = null

    try {
      // Call backend API
      const response = await modeApi.requestConsultation({
        question,
        context,
        use_rag: true,
      })

      // Convert to local format
      const consultation: ExpertConsultation = {
        id: response.id,
        question: response.question,
        context: response.context,
        timestamp: new Date(response.timestamp),
        status: response.status,
        response: response.response,
        sources: response.sources,
        confidence: response.confidence,
        confidenceScore: response.confidence_score,
        verificationNotes: response.verification_notes,
      }

      consultations.value.unshift(consultation)
      persistConsultations()

      // Show dialog for AI response
      currentConsultation.value = consultation
      showConsultationDialog.value = true

      return consultation
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to request consultation'
      // RESEARCH INTEGRITY: No fallback consultation - backend must be available
      // Don't create fake pending consultations when API fails
      throw e
    } finally {
      isLoading.value = false
    }
  }

  // Accept consultation response via API
  async function acceptConsultation(id: string, response?: string, reason?: string) {
    const consultation = consultations.value.find(c => c.id === id)
    if (consultation) {
      // Update locally first
      consultation.status = 'accepted'
      if (response) consultation.response = response
      persistConsultations()

      // Then sync to backend
      try {
        await modeApi.submitFeedback(id, {
          accepted: true,
          reason,
        })
      } catch (e) {
        console.error('Failed to sync acceptance to backend:', e)
      }
    }
    closeConsultationDialog()
  }

  // Reject consultation response via API
  async function rejectConsultation(id: string, reason?: string) {
    const consultation = consultations.value.find(c => c.id === id)
    if (consultation) {
      // Update locally first
      consultation.status = 'rejected'
      persistConsultations()

      // Then sync to backend
      try {
        await modeApi.submitFeedback(id, {
          accepted: false,
          reason,
        })
      } catch (e) {
        console.error('Failed to sync rejection to backend:', e)
      }
    }
    closeConsultationDialog()
  }

  // Close consultation dialog
  function closeConsultationDialog() {
    showConsultationDialog.value = false
    currentConsultation.value = null
  }

  // Open consultation dialog for a specific consultation
  function openConsultation(id: string) {
    const consultation = consultations.value.find(c => c.id === id)
    if (consultation) {
      currentConsultation.value = consultation
      showConsultationDialog.value = true
    }
  }

  // Clear all consultations
  function clearConsultations() {
    consultations.value = []
    persistConsultations()
  }

  // Persist consultations to session storage
  function persistConsultations() {
    sessionStorage.setItem('consultations', JSON.stringify(consultations.value))
  }

  // Execute a pre-loaded scenario
  async function executeScenario(scenarioId: string, customParams?: Record<string, unknown>) {
    isLoading.value = true
    error.value = null

    try {
      const result = await modeApi.executeScenario(scenarioId, customParams)
      // Store the result so SimulationView can access it
      lastExecutedScenario.value = result
      return result
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to execute scenario'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  // Clear the last executed scenario (called after SimulationView loads it)
  function clearLastExecutedScenario() {
    lastExecutedScenario.value = null
  }

  // Load available scenarios
  async function loadScenarios(category?: string, difficulty?: string) {
    try {
      scenarios.value = await modeApi.listScenarios(category, difficulty)
    } catch (e) {
      console.error('Failed to load scenarios:', e)
    }
  }

  // Get statistics from backend
  async function getStatistics() {
    try {
      return await modeApi.getStatistics()
    } catch (e) {
      console.error('Failed to get statistics:', e)
      return null
    }
  }

  return {
    // State
    mode,
    consultations,
    showConsultationDialog,
    currentConsultation,
    isLoading,
    error,
    llmAvailable,
    scenarios,
    lastExecutedScenario,

    // Computed
    isLLMMode,
    isNoLLMMode,
    pendingConsultations,
    hasPendingConsultations,
    acceptedConsultations,
    rejectedConsultations,

    // Actions
    initialize,
    setMode,
    toggleMode,
    requestConsultation,
    acceptConsultation,
    rejectConsultation,
    closeConsultationDialog,
    openConsultation,
    clearConsultations,
    executeScenario,
    clearLastExecutedScenario,
    loadScenarios,
    getStatistics,
  }
})

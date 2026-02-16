import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import axios from 'axios'

// LocalStorage key for chat sessions
const STORAGE_KEY = 'smart-hes-chat-sessions'
const CURRENT_SESSION_KEY = 'smart-hes-current-session'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  sources?: string[]
  confidence?: string
  isStreaming?: boolean
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: Date
  updatedAt: Date
}

interface ChatResponse {
  message: string
  session_id: string
  model: string
  confidence: string
  sources: string[]
  has_rag_context: boolean
  inference_time_ms: number
  total_time_ms: number
  timestamp: string
}

// Extended response for actionable chat requests
interface ActionResult {
  task_id: string
  task_type: string
  action: string
  success: boolean
  data?: Record<string, unknown>
  error?: string
}

// Return type for sendMessageWithAction
export interface ActionableResult {
  home?: CreatedHome
  threat?: CreatedThreat
  scenario?: CreatedScenario
}

// Created scenario structure for composite home + threat scenarios
export interface CreatedScenario {
  scenario_id: string
  name: string
  ready_to_simulate: boolean
}

interface ActionableChatResponse extends ChatResponse {
  is_actionable: boolean
  action_type?: string
  action_results: ActionResult[]
  created_resources: {
    home?: {
      id: string
      name: string
      rooms: Array<{
        id: string
        name: string
        room_type: string
        floor: number
        devices: Array<{
          id: string
          name: string
          device_type: string
        }>
      }>
      inhabitants: Array<{
        id: string
        name: string
        role: string
      }>
      total_rooms: number
      total_devices: number
      total_inhabitants: number
    }
    threat?: CreatedThreat
    scenario?: CreatedScenario
    simulation?: Record<string, unknown>
  }
}

interface ChatHealth {
  // Provider-agnostic fields (current active provider)
  provider: string  // "ollama", "openai", "gemini"
  provider_available: boolean
  provider_message: string
  available_models: string[]
  rag_enabled: boolean
  knowledge_base_documents: number
  active_sessions: number
  // Legacy fields (deprecated, kept for backwards compatibility)
  ollama_available: boolean
  ollama_message: string
}

// Created home structure for sharing with HomeBuilder
export interface CreatedHome {
  id: string
  name: string
  rooms: Array<{
    id: string
    name: string
    room_type: string
    floor: number
    devices: Array<{
      id: string
      name: string
      device_type: string
    }>
  }>
  inhabitants: Array<{
    id: string
    name: string
    role: string
  }>
  total_rooms: number
  total_devices: number
  total_inhabitants: number
}

// Created threat structure for sharing with ThreatBuilder
export interface CreatedThreat {
  id: string
  threat_type: string
  name: string
  category: string
  severity: string
  description: string
  target_device_types: string[]
  requires_network_access: boolean
  requires_physical_access: boolean
  detection_difficulty: string
  impacts: {
    data: string
    availability: string
    integrity: string
    safety: string
    financial: string
  }
  indicators: Array<{
    name: string
    description: string
    detection_method: string
  }>
  mitre_techniques: string[]
  evasion_techniques: string[]
}

// Helper functions for localStorage persistence
function loadSessionsFromStorage(): ChatSession[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return []

    const parsed = JSON.parse(saved)
    // Convert date strings back to Date objects
    return parsed.map((session: ChatSession) => ({
      ...session,
      createdAt: new Date(session.createdAt),
      updatedAt: new Date(session.updatedAt),
      messages: session.messages.map(msg => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
      })),
    }))
  } catch (e) {
    console.error('[ChatStore] Failed to load sessions from localStorage:', e)
    return []
  }
}

function saveSessionsToStorage(sessions: ChatSession[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions))
  } catch (e) {
    console.error('[ChatStore] Failed to save sessions to localStorage:', e)
  }
}

function loadCurrentSessionId(): string | null {
  try {
    return localStorage.getItem(CURRENT_SESSION_KEY)
  } catch {
    return null
  }
}

function saveCurrentSessionId(sessionId: string | null): void {
  try {
    if (sessionId) {
      localStorage.setItem(CURRENT_SESSION_KEY, sessionId)
    } else {
      localStorage.removeItem(CURRENT_SESSION_KEY)
    }
  } catch (e) {
    console.error('[ChatStore] Failed to save current session ID:', e)
  }
}

export const useChatStore = defineStore('chat', () => {
  // Load persisted state from localStorage
  const loadedSessions = loadSessionsFromStorage()
  const loadedCurrentSessionId = loadCurrentSessionId()

  // State
  const sessions = ref<ChatSession[]>(loadedSessions)
  const currentSessionId = ref<string | null>(
    // Verify loaded session ID still exists
    loadedCurrentSessionId && loadedSessions.some(s => s.id === loadedCurrentSessionId)
      ? loadedCurrentSessionId
      : loadedSessions[0]?.id ?? null
  )
  const isLoading = ref(false)
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  const health = ref<ChatHealth | null>(null)
  const useRag = ref(true)

  // Created resources from actionable requests
  const lastCreatedHome = ref<CreatedHome | null>(null)
  const lastCreatedThreat = ref<CreatedThreat | null>(null)
  const lastCreatedScenario = ref<CreatedScenario | null>(null)
  const lastActionType = ref<string | null>(null)

  // Abort controller for streaming requests (allows user to cancel)
  let currentAbortController: AbortController | null = null

  // Watch for changes and persist to localStorage
  watch(sessions, (newSessions) => {
    saveSessionsToStorage(newSessions)
  }, { deep: true })

  watch(currentSessionId, (newId) => {
    saveCurrentSessionId(newId)
  })

  // Computed
  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value)
  )

  const messages = computed(() =>
    currentSession.value?.messages ?? []
  )

  const hasMessages = computed(() => messages.value.length > 0)

  const isHealthy = computed(() => health.value?.provider_available ?? false)

  // Actions
  function generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  function createSession(title?: string): ChatSession {
    const session: ChatSession = {
      id: generateId(),
      title: title || `Chat ${sessions.value.length + 1}`,
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    }
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    return session
  }

  function selectSession(sessionId: string) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      currentSessionId.value = sessionId
    }
  }

  function deleteSession(sessionId: string) {
    const index = sessions.value.findIndex(s => s.id === sessionId)
    if (index !== -1) {
      sessions.value.splice(index, 1)
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = sessions.value[0]?.id ?? null
      }
    }
  }

  function addMessage(message: Omit<ChatMessage, 'id' | 'timestamp'>): ChatMessage {
    if (!currentSession.value) {
      createSession()
    }

    const newMessage: ChatMessage = {
      ...message,
      id: generateId(),
      timestamp: new Date(),
    }

    currentSession.value!.messages.push(newMessage)
    currentSession.value!.updatedAt = new Date()

    return newMessage
  }

  function updateMessage(messageId: string, updates: Partial<ChatMessage>) {
    if (!currentSession.value) return

    const message = currentSession.value.messages.find(m => m.id === messageId)
    if (message) {
      Object.assign(message, updates)
    }
  }

  async function sendMessage(content: string): Promise<void> {
    if (!content.trim()) return

    error.value = null

    // Create session if needed
    if (!currentSession.value) {
      createSession()
    }

    // Add user message
    addMessage({
      role: 'user',
      content: content.trim(),
    })

    isLoading.value = true

    try {
      const response = await axios.post<ChatResponse>('/api/chat/', {
        message: content,
        session_id: currentSessionId.value,
        use_rag: useRag.value,
      })

      // Add assistant message
      addMessage({
        role: 'assistant',
        content: response.data.message,
        sources: response.data.sources,
        confidence: response.data.confidence,
      })

      // Update session title from first message
      if (currentSession.value && currentSession.value.messages.length === 2) {
        currentSession.value.title = content.substring(0, 50) + (content.length > 50 ? '...' : '')
      }

    } catch (e) {
      const errorMessage = axios.isAxiosError(e)
        ? e.response?.data?.detail || e.message
        : 'Failed to send message'

      error.value = errorMessage

      // Add error message
      addMessage({
        role: 'assistant',
        content: `Error: ${errorMessage}`,
      })
    } finally {
      isLoading.value = false
    }
  }

  async function sendMessageStream(content: string): Promise<void> {
    if (!content.trim()) return

    error.value = null

    // Create session if needed
    if (!currentSession.value) {
      createSession()
    }

    // Add user message
    addMessage({
      role: 'user',
      content: content.trim(),
    })

    // Add placeholder assistant message for streaming
    const assistantMessage = addMessage({
      role: 'assistant',
      content: '',
      isStreaming: true,
    })

    isLoading.value = true
    isStreaming.value = true

    // Create abort controller for timeout and manual cancellation
    currentAbortController = new AbortController()
    const timeoutId = setTimeout(() => currentAbortController?.abort(), 300000) // 5 minute timeout

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          session_id: currentSessionId.value,
          use_rag: useRag.value,
        }),
        signal: currentAbortController.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let fullContent = ''
      let sources: string[] = []
      let buffer = '' // Buffer for incomplete SSE data

      // Listen for abort signal to cancel the reader
      const abortHandler = () => {
        reader.cancel()
      }
      currentAbortController?.signal.addEventListener('abort', abortHandler)

      try {
        while (true) {
          // Check if aborted before each read
          if (currentAbortController?.signal.aborted) {
            throw new DOMException('Aborted', 'AbortError')
          }

          const { done, value } = await reader.read()
          if (done) break

          // Append new chunk to buffer and process complete lines
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')

          // Keep the last potentially incomplete line in buffer
          buffer = lines.pop() || ''

          for (const line of lines) {
            const trimmedLine = line.trim()
            if (trimmedLine.startsWith('data: ')) {
              try {
                const jsonStr = trimmedLine.slice(6)
                if (!jsonStr) continue

                const data = JSON.parse(jsonStr)

                if (data.error) {
                  throw new Error(data.error)
                }

                if (data.content) {
                  fullContent += data.content
                  updateMessage(assistantMessage.id, { content: fullContent })
                }

                if (data.done && data.sources) {
                  sources = data.sources
                }
              } catch (parseError) {
                // Skip non-JSON lines or incomplete JSON
                console.debug('SSE parse skip:', trimmedLine)
              }
            }
          }
        }
      } finally {
        currentAbortController?.signal.removeEventListener('abort', abortHandler)
      }

      // Process any remaining data in buffer
      if (buffer.trim().startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.trim().slice(6))
          if (data.content) {
            fullContent += data.content
          }
          if (data.sources) {
            sources = data.sources
          }
        } catch {
          // Ignore incomplete final chunk
        }
      }

      // Finalize the message
      updateMessage(assistantMessage.id, {
        content: fullContent,
        sources,
        isStreaming: false,
      })

      // Update session title from first message
      if (currentSession.value && currentSession.value.messages.length === 2) {
        currentSession.value.title = content.substring(0, 50) + (content.length > 50 ? '...' : '')
      }

    } catch (e) {
      // Check if this was a user-initiated abort (can be DOMException or Error with name AbortError)
      const isAbort = (e instanceof DOMException && e.name === 'AbortError') ||
                      (e instanceof Error && e.name === 'AbortError') ||
                      (e instanceof TypeError && e.message.includes('cancel'))

      if (isAbort) {
        // User cancelled - keep what we have so far (or show stopped message)
        const currentContent = currentSession.value?.messages.find(m => m.id === assistantMessage.id)?.content
        updateMessage(assistantMessage.id, {
          content: currentContent ? currentContent + '\n\n*(Generation stopped)*' : '(Generation stopped by user)',
          isStreaming: false,
        })
      } else {
        const errorMessage = e instanceof Error ? e.message : 'Failed to send message'
        error.value = errorMessage

        updateMessage(assistantMessage.id, {
          content: `Error: ${errorMessage}`,
          isStreaming: false,
        })
      }
    } finally {
      isLoading.value = false
      isStreaming.value = false
      currentAbortController = null
    }
  }

  function stopGeneration(): void {
    if (currentAbortController) {
      currentAbortController.abort()
      currentAbortController = null
    }
  }

  async function fetchHealth(): Promise<void> {
    try {
      const response = await axios.get<ChatHealth>('/api/chat/health')
      health.value = response.data
    } catch (e) {
      health.value = null
      error.value = 'Failed to fetch chat health status'
    }
  }

  function clearError() {
    error.value = null
  }

  function clearCurrentSession() {
    if (currentSession.value) {
      currentSession.value.messages = []
      currentSession.value.updatedAt = new Date()
    }
  }

  function toggleRag() {
    useRag.value = !useRag.value
  }

  /**
   * Send a message using the actionable chat endpoint.
   * This endpoint detects actionable requests (like "build a home" or "create a threat") and executes them.
   * Returns information about any created resources (homes, threats, simulations, etc.)
   */
  async function sendMessageWithAction(content: string): Promise<ActionableResult | null> {
    if (!content.trim()) return null

    error.value = null
    lastCreatedHome.value = null
    lastCreatedThreat.value = null
    lastCreatedScenario.value = null
    lastActionType.value = null

    // Create session if needed
    if (!currentSession.value) {
      createSession()
    }

    // Add user message
    addMessage({
      role: 'user',
      content: content.trim(),
    })

    isLoading.value = true

    try {
      const response = await axios.post<ActionableChatResponse>('/api/chat/action', {
        message: content,
        session_id: currentSessionId.value,
        use_rag: useRag.value,
      })

      // Add assistant message
      addMessage({
        role: 'assistant',
        content: response.data.message,
        sources: response.data.sources,
        confidence: response.data.confidence,
      })

      // Update session title from first message
      if (currentSession.value && currentSession.value.messages.length === 2) {
        currentSession.value.title = content.substring(0, 50) + (content.length > 50 ? '...' : '')
      }

      // Handle actionable response
      if (response.data.is_actionable) {
        lastActionType.value = response.data.action_type || null
        const result: ActionableResult = {}

        // If a home was created, store it
        if (response.data.created_resources?.home) {
          lastCreatedHome.value = response.data.created_resources.home
          result.home = response.data.created_resources.home
        }

        // If a threat was created (either from inject_threat or create_scenario)
        if (response.data.created_resources?.threat) {
          lastCreatedThreat.value = response.data.created_resources.threat
          result.threat = response.data.created_resources.threat
        } else if (response.data.action_type === 'inject_threat') {
          // Legacy: extract threat from action_results for inject_threat action
          const threatResult = response.data.action_results.find(
            r => r.action === 'inject_threat' && r.success && r.data
          )
          if (threatResult?.data && !('available_threats' in threatResult.data)) {
            // This is a specific threat creation, not a list of available threats
            lastCreatedThreat.value = threatResult.data as unknown as CreatedThreat
            result.threat = threatResult.data as unknown as CreatedThreat
          }
        }

        // If a scenario was created (composite home + threat)
        if (response.data.created_resources?.scenario) {
          lastCreatedScenario.value = response.data.created_resources.scenario
          result.scenario = response.data.created_resources.scenario
        }

        // Return result if any resources were created
        if (result.home || result.threat || result.scenario) {
          return result
        }
      }

      return null

    } catch (e) {
      const errorMessage = axios.isAxiosError(e)
        ? e.response?.data?.detail || e.message
        : 'Failed to send message'

      error.value = errorMessage

      // Add error message
      addMessage({
        role: 'assistant',
        content: `Error: ${errorMessage}`,
      })

      return null
    } finally {
      isLoading.value = false
    }
  }

  function clearCreatedResources() {
    lastCreatedHome.value = null
    lastCreatedThreat.value = null
    lastCreatedScenario.value = null
    lastActionType.value = null
  }

  return {
    // State
    sessions,
    currentSessionId,
    isLoading,
    isStreaming,
    error,
    health,
    useRag,
    lastCreatedHome,
    lastCreatedThreat,
    lastCreatedScenario,
    lastActionType,

    // Computed
    currentSession,
    messages,
    hasMessages,
    isHealthy,

    // Actions
    createSession,
    selectSession,
    deleteSession,
    addMessage,
    sendMessage,
    sendMessageStream,
    sendMessageWithAction,
    stopGeneration,
    fetchHealth,
    clearError,
    clearCurrentSession,
    clearCreatedResources,
    toggleRag,
  }
})

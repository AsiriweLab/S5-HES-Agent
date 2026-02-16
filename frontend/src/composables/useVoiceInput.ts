import { ref, onUnmounted } from 'vue'

// Web Speech API type definitions
interface SpeechRecognitionEvent extends Event {
  resultIndex: number
  results: SpeechRecognitionResultList
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string
  message: string
}

interface SpeechRecognitionInstance extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  onstart: (() => void) | null
  onend: (() => void) | null
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}

interface SpeechRecognitionConstructor {
  new (): SpeechRecognitionInstance
}

export interface UseVoiceInputOptions {
  language?: string
  continuous?: boolean
  interimResults?: boolean
  onResult?: (transcript: string, isFinal: boolean) => void
  onError?: (error: string) => void
  onStart?: () => void
  onEnd?: () => void
}

export interface UseVoiceInputReturn {
  isSupported: boolean
  isListening: ReturnType<typeof ref<boolean>>
  transcript: ReturnType<typeof ref<string>>
  interimTranscript: ReturnType<typeof ref<string>>
  error: ReturnType<typeof ref<string | null>>
  start: () => void
  stop: () => void
  toggle: () => void
  reset: () => void
}

/**
 * Composable for Web Speech API voice input integration
 * Provides speech-to-text functionality for the chat interface
 */
export function useVoiceInput(options: UseVoiceInputOptions = {}): UseVoiceInputReturn {
  const {
    language = 'en-US',
    continuous = false,
    interimResults = true,
    onResult,
    onError,
    onStart,
    onEnd,
  } = options

  // Check for browser support
  const SpeechRecognitionAPI =
    (window as unknown as { SpeechRecognition?: SpeechRecognitionConstructor }).SpeechRecognition ||
    (window as unknown as { webkitSpeechRecognition?: SpeechRecognitionConstructor }).webkitSpeechRecognition

  const isSupported = !!SpeechRecognitionAPI

  // State
  const isListening = ref(false)
  const transcript = ref('')
  const interimTranscript = ref('')
  const error = ref<string | null>(null)

  // Recognition instance
  let recognition: SpeechRecognitionInstance | null = null

  if (isSupported && SpeechRecognitionAPI) {
    recognition = new SpeechRecognitionAPI()
    recognition.lang = language
    recognition.continuous = continuous
    recognition.interimResults = interimResults

    recognition.onstart = () => {
      isListening.value = true
      error.value = null
      onStart?.()
    }

    recognition.onend = () => {
      isListening.value = false
      onEnd?.()
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = ''
      let interim = ''

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          finalTranscript += result[0].transcript
        } else {
          interim += result[0].transcript
        }
      }

      if (finalTranscript) {
        transcript.value += finalTranscript
        onResult?.(finalTranscript, true)
      }

      interimTranscript.value = interim
      if (interim) {
        onResult?.(interim, false)
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const errorMessages: Record<string, string> = {
        'no-speech': 'No speech was detected. Please try again.',
        'audio-capture': 'No microphone was found. Ensure it is plugged in.',
        'not-allowed': 'Microphone permission was denied. Please allow access.',
        'network': 'A network error occurred. Please check your connection.',
        'aborted': 'Speech recognition was aborted.',
        'service-not-allowed': 'Speech recognition service is not allowed.',
      }

      const message = errorMessages[event.error] || `Speech recognition error: ${event.error}`
      error.value = message
      isListening.value = false
      onError?.(message)
    }
  }

  function start() {
    if (!isSupported || !recognition) {
      error.value = 'Speech recognition is not supported in this browser'
      return
    }

    if (isListening.value) return

    try {
      transcript.value = ''
      interimTranscript.value = ''
      recognition.start()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to start speech recognition'
    }
  }

  function stop() {
    if (!recognition || !isListening.value) return

    try {
      recognition.stop()
    } catch (e) {
      // Ignore errors when stopping
    }
  }

  function toggle() {
    if (isListening.value) {
      stop()
    } else {
      start()
    }
  }

  function reset() {
    stop()
    transcript.value = ''
    interimTranscript.value = ''
    error.value = null
  }

  // Cleanup on unmount
  onUnmounted(() => {
    if (recognition && isListening.value) {
      recognition.stop()
    }
  })

  return {
    isSupported,
    isListening,
    transcript,
    interimTranscript,
    error,
    start,
    stop,
    toggle,
    reset,
  }
}

/**
 * Utility hook for voice command detection
 * Listens for specific command patterns and triggers callbacks
 */
export interface VoiceCommand {
  patterns: string[] | RegExp
  callback: (match: string) => void
}

export interface UseVoiceCommandsOptions {
  language?: string
  commands: VoiceCommand[]
  onUnrecognized?: (transcript: string) => void
}

export function useVoiceCommands(options: UseVoiceCommandsOptions) {
  const { language = 'en-US', commands, onUnrecognized } = options

  const lastCommand = ref<string | null>(null)
  const isProcessing = ref(false)

  const voice = useVoiceInput({
    language,
    continuous: true,
    interimResults: false,
    onResult: (transcript, isFinal) => {
      if (!isFinal) return

      isProcessing.value = true
      const normalizedTranscript = transcript.toLowerCase().trim()

      let matched = false

      for (const command of commands) {
        if (Array.isArray(command.patterns)) {
          // String pattern matching
          for (const pattern of command.patterns) {
            if (normalizedTranscript.includes(pattern.toLowerCase())) {
              lastCommand.value = pattern
              command.callback(normalizedTranscript)
              matched = true
              break
            }
          }
        } else {
          // RegExp matching
          const match = normalizedTranscript.match(command.patterns)
          if (match) {
            lastCommand.value = match[0]
            command.callback(normalizedTranscript)
            matched = true
          }
        }

        if (matched) break
      }

      if (!matched && onUnrecognized) {
        onUnrecognized(transcript)
      }

      isProcessing.value = false
    },
  })

  return {
    ...voice,
    lastCommand,
    isProcessing,
  }
}

// Type declarations for Web Speech API (for TypeScript)
declare global {
  interface Window {
    SpeechRecognition: SpeechRecognitionConstructor
    webkitSpeechRecognition: SpeechRecognitionConstructor
  }
}

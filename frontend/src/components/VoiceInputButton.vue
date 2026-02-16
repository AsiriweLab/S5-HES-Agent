<script setup lang="ts">
import { watch } from 'vue'
import { useVoiceInput } from '@/composables/useVoiceInput'

defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  transcript: [text: string]
  interimTranscript: [text: string]
  error: [message: string]
}>()

const {
  isSupported,
  isListening,
  error,
  toggle,
} = useVoiceInput({
  continuous: false,
  interimResults: true,
  onResult: (text, isFinal) => {
    if (isFinal) {
      emit('transcript', text)
    } else {
      emit('interimTranscript', text)
    }
  },
  onError: (message) => {
    emit('error', message)
  },
})

watch(error, (newError) => {
  if (newError) {
    emit('error', newError)
  }
})
</script>

<template>
  <button
    v-if="isSupported"
    class="voice-btn btn btn-ghost btn-icon"
    :class="{ listening: isListening }"
    :disabled="disabled"
    @click="toggle"
    :title="isListening ? 'Stop listening' : 'Start voice input'"
  >
    <svg v-if="isListening" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
      <line x1="12" y1="19" x2="12" y2="23"></line>
      <line x1="8" y1="23" x2="16" y2="23"></line>
    </svg>
    <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
      <line x1="12" y1="19" x2="12" y2="23"></line>
      <line x1="8" y1="23" x2="16" y2="23"></line>
    </svg>

    <span v-if="isListening" class="pulse-ring"></span>
  </button>

  <span v-else class="voice-unsupported" title="Voice input not supported in this browser">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="1" y1="1" x2="23" y2="23"></line>
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"></path>
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"></path>
      <line x1="12" y1="19" x2="12" y2="23"></line>
      <line x1="8" y1="23" x2="16" y2="23"></line>
    </svg>
  </span>
</template>

<style scoped>
.voice-btn {
  position: relative;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.voice-btn:hover {
  color: var(--color-primary);
}

.voice-btn.listening {
  color: var(--color-error);
  background: rgba(239, 68, 68, 0.1);
}

.pulse-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid var(--color-error);
  animation: pulse 1.5s ease-out infinite;
  pointer-events: none;
}

@keyframes pulse {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(1.5);
    opacity: 0;
  }
}

.voice-unsupported {
  color: var(--text-muted);
  padding: var(--spacing-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>

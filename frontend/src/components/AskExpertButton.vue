<script setup lang="ts">
import { ref } from 'vue'
import { useModeStore } from '@/stores/mode'

const modeStore = useModeStore()

const showQuestionInput = ref(false)
const question = ref('')
const isSubmitting = ref(false)
const errorMessage = ref<string | null>(null)

function openQuestionInput() {
  showQuestionInput.value = true
  errorMessage.value = null
}

function closeQuestionInput() {
  showQuestionInput.value = false
  question.value = ''
  errorMessage.value = null
}

async function submitQuestion() {
  if (!question.value.trim()) return

  isSubmitting.value = true
  errorMessage.value = null

  try {
    // Request consultation via API (will show dialog with response)
    await modeStore.requestConsultation(
      question.value.trim(),
      'User requested expert consultation from Manual Mode'
    )

    // Close the input panel - the consultation dialog will be shown by the store
    closeQuestionInput()
  } catch (e) {
    errorMessage.value = e instanceof Error ? e.message : 'Failed to get expert advice. Please try again.'
    console.error('Consultation request failed:', e)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="ask-expert">
    <!-- Trigger Button -->
    <button
      v-if="!showQuestionInput"
      class="btn btn-secondary ask-btn"
      @click="openQuestionInput"
      title="Ask AI Expert for guidance"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
      <span>Ask Expert</span>
    </button>

    <!-- Question Input Panel -->
    <div v-else class="question-panel card">
      <div class="panel-header">
        <h4>Ask AI Expert</h4>
        <button class="btn btn-ghost btn-icon" @click="closeQuestionInput">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <p class="panel-description">
        Get AI-powered guidance with RAG-augmented verification.
        The response will include sources and confidence scoring.
        You can accept or reject the suggestion.
      </p>

      <!-- Error Message -->
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>

      <textarea
        v-model="question"
        class="input question-input"
        placeholder="What would you like help with? (e.g., 'How do I detect botnet traffic?')"
        rows="3"
        :disabled="isSubmitting"
      ></textarea>

      <div class="panel-info">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
        <span>Response will be verified against the knowledge base</span>
      </div>

      <div class="panel-actions">
        <button class="btn btn-ghost" @click="closeQuestionInput" :disabled="isSubmitting">
          Cancel
        </button>
        <button
          class="btn btn-primary"
          @click="submitQuestion"
          :disabled="!question.trim() || isSubmitting"
        >
          <span v-if="isSubmitting" class="spinner"></span>
          <span v-else>Get Expert Advice</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ask-expert {
  position: relative;
}

.ask-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.question-panel {
  position: absolute;
  top: calc(100% + var(--spacing-sm));
  right: 0;
  width: 360px;
  z-index: 100;
  animation: slideDown 0.2s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.panel-header h4 {
  margin: 0;
  font-size: 1rem;
}

.panel-description {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
  line-height: 1.4;
}

.error-message {
  background: var(--danger-bg, #fee2e2);
  color: var(--danger, #dc2626);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  margin-bottom: var(--spacing-md);
}

.question-input {
  resize: vertical;
  min-height: 80px;
  margin-bottom: var(--spacing-sm);
}

.panel-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-md);
}

.panel-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

<script setup lang="ts">
import { computed } from 'vue'
import { useModeStore } from '@/stores/mode'

const modeStore = useModeStore()

const isLLMMode = computed(() => modeStore.isLLMMode)
const modeName = computed(() => isLLMMode.value ? 'LLM-Assisted' : 'Manual Mode')
</script>

<template>
  <div class="mode-indicator" :class="{ 'llm-mode': isLLMMode, 'manual-mode': !isLLMMode }">
    <svg v-if="isLLMMode" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
    </svg>
    <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
    </svg>
    <span class="mode-name">{{ modeName }}</span>
  </div>
</template>

<style scoped>
.mode-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.mode-indicator.llm-mode {
  background: rgba(0, 217, 255, 0.15);
  color: var(--color-primary);
}

.mode-indicator.manual-mode {
  background: rgba(245, 158, 11, 0.15);
  color: var(--color-warning);
}

.mode-name {
  white-space: nowrap;
}

@media (max-width: 600px) {
  .mode-name {
    display: none;
  }
}
</style>

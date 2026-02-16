<script setup lang="ts">
import { computed } from 'vue'
import { useModeStore } from '@/stores/mode'

const modeStore = useModeStore()

const isLLMMode = computed(() => modeStore.isLLMMode)

function toggleMode() {
  modeStore.toggleMode()
}
</script>

<template>
  <div class="mode-controller">
    <button
      class="mode-toggle"
      @click="toggleMode"
      :title="isLLMMode ? 'Switch to Manual Mode' : 'Switch to LLM Mode'"
    >
      <div class="toggle-track" :class="{ 'llm-active': isLLMMode }">
        <div class="toggle-thumb"></div>
      </div>
      <div class="toggle-labels">
        <span class="label" :class="{ active: !isLLMMode }">Manual</span>
        <span class="label" :class="{ active: isLLMMode }">LLM</span>
      </div>
    </button>
  </div>
</template>

<style scoped>
.mode-controller {
  display: flex;
  align-items: center;
}

.mode-toggle {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.mode-toggle:hover {
  border-color: var(--color-primary);
}

.toggle-track {
  position: relative;
  width: 36px;
  height: 20px;
  background: var(--text-muted);
  border-radius: var(--radius-full);
  transition: background var(--transition-fast);
}

.toggle-track.llm-active {
  background: var(--color-primary);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  background: white;
  border-radius: 50%;
  transition: transform var(--transition-fast);
}

.toggle-track.llm-active .toggle-thumb {
  transform: translateX(16px);
}

.toggle-labels {
  display: flex;
  gap: var(--spacing-xs);
}

.label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-muted);
  transition: color var(--transition-fast);
}

.label.active {
  color: var(--color-primary);
}
</style>

<script setup lang="ts">
defineProps<{
  variant?: 'spinner' | 'dots' | 'pulse' | 'bars' | 'typing'
  size?: 'sm' | 'md' | 'lg'
  text?: string
}>()
</script>

<template>
  <div class="loading-state" :class="`loading-${size || 'md'}`">
    <!-- Spinner -->
    <div v-if="variant === 'spinner' || !variant" class="spinner"></div>

    <!-- Dots -->
    <div v-else-if="variant === 'dots'" class="dots">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <!-- Pulse -->
    <div v-else-if="variant === 'pulse'" class="pulse">
      <span></span>
    </div>

    <!-- Bars -->
    <div v-else-if="variant === 'bars'" class="bars">
      <span></span>
      <span></span>
      <span></span>
      <span></span>
    </div>

    <!-- Typing Indicator -->
    <div v-else-if="variant === 'typing'" class="typing">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <span v-if="text" class="loading-text">{{ text }}</span>
  </div>
</template>

<style scoped>
.loading-state {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  color: var(--text-secondary);
}

.loading-text {
  font-size: 0.875rem;
}

/* Size variants */
.loading-sm {
  --loader-size: 16px;
}

.loading-md {
  --loader-size: 24px;
}

.loading-lg {
  --loader-size: 32px;
}

/* Spinner */
.spinner {
  width: var(--loader-size);
  height: var(--loader-size);
  border: 2px solid var(--border-color);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Dots */
.dots {
  display: flex;
  gap: 4px;
}

.dots span {
  width: calc(var(--loader-size) / 3);
  height: calc(var(--loader-size) / 3);
  background: var(--color-primary);
  border-radius: 50%;
  animation: bounce 1.4s ease-in-out infinite both;
}

.dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

/* Pulse */
.pulse span {
  display: block;
  width: var(--loader-size);
  height: var(--loader-size);
  background: var(--color-primary);
  border-radius: 50%;
  animation: pulse-anim 1.5s ease-in-out infinite;
}

@keyframes pulse-anim {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  50% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
}

/* Bars */
.bars {
  display: flex;
  gap: 3px;
  height: var(--loader-size);
  align-items: center;
}

.bars span {
  width: calc(var(--loader-size) / 6);
  height: 60%;
  background: var(--color-primary);
  border-radius: 2px;
  animation: bars-anim 1.2s ease-in-out infinite;
}

.bars span:nth-child(1) {
  animation-delay: 0s;
}

.bars span:nth-child(2) {
  animation-delay: 0.1s;
}

.bars span:nth-child(3) {
  animation-delay: 0.2s;
}

.bars span:nth-child(4) {
  animation-delay: 0.3s;
}

@keyframes bars-anim {
  0%, 40%, 100% {
    height: 40%;
  }
  20% {
    height: 100%;
  }
}

/* Typing Indicator */
.typing {
  display: flex;
  gap: 4px;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-input);
  border-radius: var(--radius-md);
}

.typing span {
  width: 8px;
  height: 8px;
  background: var(--text-muted);
  border-radius: 50%;
  animation: typing-anim 1.4s ease-in-out infinite;
}

.typing span:nth-child(1) {
  animation-delay: 0s;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-anim {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
</style>

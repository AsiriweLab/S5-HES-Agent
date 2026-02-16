<script setup lang="ts">
defineProps<{
  variant?: 'text' | 'avatar' | 'card' | 'button' | 'input' | 'paragraph'
  width?: string
  height?: string
  lines?: number
  animated?: boolean
}>()
</script>

<template>
  <div
    class="skeleton"
    :class="[
      `skeleton-${variant || 'text'}`,
      { 'skeleton-animated': animated !== false }
    ]"
    :style="{
      width: width,
      height: height,
    }"
  >
    <template v-if="variant === 'paragraph' && lines">
      <div
        v-for="i in lines"
        :key="i"
        class="skeleton-line"
        :style="{ width: i === lines ? '60%' : '100%' }"
      ></div>
    </template>
  </div>
</template>

<style scoped>
.skeleton {
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  position: relative;
  overflow: hidden;
}

.skeleton-animated::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.08),
    transparent
  );
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* Variants */
.skeleton-text {
  height: 1em;
  width: 100%;
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}

.skeleton-card {
  height: 120px;
  width: 100%;
  border-radius: var(--radius-md);
}

.skeleton-button {
  height: 36px;
  width: 100px;
  border-radius: var(--radius-sm);
}

.skeleton-input {
  height: 40px;
  width: 100%;
  border-radius: var(--radius-sm);
}

.skeleton-paragraph {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  background: transparent;
}

.skeleton-paragraph::after {
  display: none;
}

.skeleton-line {
  height: 1em;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  position: relative;
  overflow: hidden;
}

.skeleton-animated .skeleton-line::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.08),
    transparent
  );
  animation: shimmer 1.5s infinite;
}
</style>

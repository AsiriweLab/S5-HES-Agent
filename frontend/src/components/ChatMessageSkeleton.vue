<script setup lang="ts">
import SkeletonLoader from './SkeletonLoader.vue'

defineProps<{
  role?: 'user' | 'assistant'
}>()
</script>

<template>
  <div class="message-skeleton" :class="[role || 'assistant']">
    <div class="avatar-skeleton">
      <SkeletonLoader variant="avatar" />
    </div>
    <div class="content-skeleton">
      <div class="header-skeleton">
        <SkeletonLoader variant="text" width="80px" />
        <SkeletonLoader variant="text" width="60px" />
      </div>
      <div class="body-skeleton">
        <SkeletonLoader variant="paragraph" :lines="3" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-skeleton {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.message-skeleton.user {
  flex-direction: row-reverse;
}

.avatar-skeleton {
  flex-shrink: 0;
}

.content-skeleton {
  flex: 1;
  max-width: 70%;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.header-skeleton {
  display: flex;
  gap: var(--spacing-sm);
}

.message-skeleton.user .header-skeleton {
  justify-content: flex-end;
}

.body-skeleton {
  background: var(--bg-input);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
}

.message-skeleton.user .body-skeleton {
  background: rgba(59, 130, 246, 0.1);
}
</style>

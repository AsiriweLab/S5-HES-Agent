<script setup lang="ts">
import SkeletonLoader from './SkeletonLoader.vue'
</script>

<template>
  <div class="device-card-skeleton">
    <div class="card-header">
      <SkeletonLoader variant="avatar" width="48px" height="48px" />
      <div class="card-title">
        <SkeletonLoader variant="text" width="120px" />
        <SkeletonLoader variant="text" width="80px" height="0.75em" />
      </div>
      <SkeletonLoader variant="button" width="40px" height="40px" />
    </div>
    <div class="card-body">
      <SkeletonLoader variant="text" width="100%" />
      <SkeletonLoader variant="text" width="70%" />
    </div>
    <div class="card-footer">
      <SkeletonLoader variant="text" width="60px" height="0.75em" />
      <SkeletonLoader variant="button" width="32px" height="20px" />
    </div>
  </div>
</template>

<style scoped>
.device-card-skeleton {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.card-title {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
}
</style>

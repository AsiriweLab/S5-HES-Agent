<script setup lang="ts">
import SkeletonLoader from './SkeletonLoader.vue'
import DeviceCardSkeleton from './DeviceCardSkeleton.vue'

defineProps<{
  deviceCount?: number
}>()
</script>

<template>
  <div class="dashboard-skeleton">
    <!-- Stats Row -->
    <div class="stats-row">
      <div v-for="i in 4" :key="i" class="stat-card-skeleton">
        <div class="stat-icon">
          <SkeletonLoader variant="avatar" width="40px" height="40px" />
        </div>
        <div class="stat-content">
          <SkeletonLoader variant="text" width="60px" height="1.5em" />
          <SkeletonLoader variant="text" width="100px" height="0.75em" />
        </div>
      </div>
    </div>

    <!-- Section Header -->
    <div class="section-header">
      <SkeletonLoader variant="text" width="150px" height="1.25em" />
      <SkeletonLoader variant="button" width="100px" />
    </div>

    <!-- Device Grid -->
    <div class="device-grid">
      <DeviceCardSkeleton v-for="i in (deviceCount || 6)" :key="i" />
    </div>
  </div>
</template>

<style scoped>
.dashboard-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-md);
}

.stat-card-skeleton {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.device-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-md);
}
</style>

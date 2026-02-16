import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

interface HealthResponse {
  status: string
  timestamp: string
  version: string
  environment: string
}

export const useHealthStore = defineStore('health', () => {
  const health = ref<HealthResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isHealthy = computed(() => health.value?.status === 'healthy')

  async function fetchHealth() {
    loading.value = true
    error.value = null

    try {
      const response = await axios.get<HealthResponse>('/api/health')
      health.value = response.data
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch health status'
      health.value = null
    } finally {
      loading.value = false
    }
  }

  return {
    health,
    loading,
    error,
    isHealthy,
    fetchHealth,
  }
})

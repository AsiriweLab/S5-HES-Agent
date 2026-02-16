import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  adminApi,
  type User,
  type ApiKey,
  type ConfigItem,
  type AuditLog,
  type SystemStats,
  type LoginResponse,
} from '@/services/adminApi'

export const useAdminStore = defineStore('admin', () => {
  // ==========================================================================
  // State
  // ==========================================================================

  // Auth state
  const isAuthenticated = ref(false)
  const currentUser = ref<User | null>(null)
  const sessionExpiry = ref<Date | null>(null)

  // Data state
  const users = ref<User[]>([])
  const apiKeys = ref<ApiKey[]>([])
  const configs = ref<ConfigItem[]>([])
  const auditLogs = ref<AuditLog[]>([])
  const systemStats = ref<SystemStats | null>(null)

  // UI state
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isApiAvailable = ref(false)

  // ==========================================================================
  // Computed
  // ==========================================================================

  const isAdmin = computed(() => currentUser.value?.role === 'admin')

  const activeUsers = computed(() => users.value.filter(u => u.status === 'active'))

  const activeApiKeys = computed(() => apiKeys.value.filter(k => k.status === 'active'))

  const configCategories = computed(() => {
    const categories = new Set(configs.value.map(c => c.category))
    return Array.from(categories)
  })

  const groupedConfigs = computed(() => {
    const grouped: Record<string, ConfigItem[]> = {}
    configs.value.forEach(config => {
      if (!grouped[config.category]) {
        grouped[config.category] = []
      }
      grouped[config.category].push(config)
    })
    return grouped
  })

  // ==========================================================================
  // Actions
  // ==========================================================================

  async function checkApiAvailability(): Promise<boolean> {
    try {
      isApiAvailable.value = await adminApi.checkAvailability()
      return isApiAvailable.value
    } catch {
      isApiAvailable.value = false
      return false
    }
  }

  async function initialize(): Promise<void> {
    // Check if already logged in
    if (adminApi.isLoggedIn()) {
      try {
        const user = await adminApi.getCurrentUser()
        currentUser.value = user
        isAuthenticated.value = true
        // Load initial data
        await Promise.all([
          loadSystemStats(),
          loadUsers(),
          loadApiKeys(),
          loadConfig(),
          loadAuditLogs(),
        ])
      } catch {
        // Session expired
        isAuthenticated.value = false
        currentUser.value = null
      }
    }
  }

  async function login(username: string, password: string): Promise<LoginResponse> {
    isLoading.value = true
    error.value = null

    try {
      const response = await adminApi.login(username, password)
      isAuthenticated.value = true
      sessionExpiry.value = new Date(response.expires_at)

      // Get user details
      currentUser.value = await adminApi.getCurrentUser()

      // Load initial data
      await Promise.all([
        loadSystemStats(),
        loadUsers(),
        loadApiKeys(),
        loadConfig(),
        loadAuditLogs(),
      ])

      return response
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Login failed'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function logout(): Promise<void> {
    await adminApi.logout()
    isAuthenticated.value = false
    currentUser.value = null
    sessionExpiry.value = null
    users.value = []
    apiKeys.value = []
    configs.value = []
    auditLogs.value = []
    systemStats.value = null
  }

  async function loadSystemStats(): Promise<void> {
    try {
      systemStats.value = await adminApi.getOverview()
    } catch (err) {
      console.error('Failed to load system stats:', err)
    }
  }

  async function loadUsers(): Promise<void> {
    try {
      users.value = await adminApi.listUsers()
    } catch (err) {
      console.error('Failed to load users:', err)
    }
  }

  async function createUser(username: string, email: string, password: string, role: 'admin' | 'user' | 'viewer'): Promise<User> {
    isLoading.value = true
    error.value = null

    try {
      const user = await adminApi.createUser({ username, email, password, role })
      users.value.push(user)
      await loadAuditLogs() // Refresh audit logs
      return user
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create user'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function updateUser(userId: string, updates: { email?: string; role?: string; status?: string }): Promise<User> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await adminApi.updateUser(userId, updates)
      const index = users.value.findIndex(u => u.id === userId)
      if (index !== -1) {
        users.value[index] = updated
      }
      await loadAuditLogs() // Refresh audit logs
      return updated
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update user'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function deleteUser(userId: string): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await adminApi.deleteUser(userId)
      users.value = users.value.filter(u => u.id !== userId)
      await loadAuditLogs() // Refresh audit logs
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to delete user'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function loadApiKeys(): Promise<void> {
    try {
      apiKeys.value = await adminApi.listApiKeys()
    } catch (err) {
      console.error('Failed to load API keys:', err)
    }
  }

  async function createApiKey(name: string, permissions: string[]): Promise<ApiKey> {
    isLoading.value = true
    error.value = null

    try {
      const key = await adminApi.createApiKey({ name, permissions })
      apiKeys.value.push(key)
      await loadAuditLogs() // Refresh audit logs
      return key
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to create API key'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function revokeApiKey(keyId: string): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await adminApi.revokeApiKey(keyId)
      const key = apiKeys.value.find(k => k.id === keyId)
      if (key) {
        key.status = 'revoked'
      }
      await loadAuditLogs() // Refresh audit logs
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to revoke API key'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function loadConfig(): Promise<void> {
    try {
      configs.value = await adminApi.getConfig()
    } catch (err) {
      console.error('Failed to load config:', err)
    }
  }

  async function updateConfig(key: string, value: string | number | boolean): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const updated = await adminApi.updateConfig(key, value)
      const index = configs.value.findIndex(c => c.key === key)
      if (index !== -1) {
        configs.value[index] = updated
      }
      await loadAuditLogs() // Refresh audit logs
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update config'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function loadAuditLogs(options: { limit?: number; action?: string; user?: string } = {}): Promise<void> {
    try {
      auditLogs.value = await adminApi.getAuditLogs({ limit: 100, ...options })
    } catch (err) {
      console.error('Failed to load audit logs:', err)
    }
  }

  async function clearCache(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await adminApi.clearCache()
      await loadAuditLogs() // Refresh audit logs
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to clear cache'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function exportConfig(): Promise<{ configs: { key: string; value: unknown }[]; exported_at: string; exported_by: string }> {
    isLoading.value = true
    error.value = null

    try {
      const result = await adminApi.exportConfig()
      await loadAuditLogs() // Refresh audit logs
      return result
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to export config'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // ==========================================================================
  // Return
  // ==========================================================================

  return {
    // State
    isAuthenticated,
    currentUser,
    sessionExpiry,
    users,
    apiKeys,
    configs,
    auditLogs,
    systemStats,
    isLoading,
    error,
    isApiAvailable,

    // Computed
    isAdmin,
    activeUsers,
    activeApiKeys,
    configCategories,
    groupedConfigs,

    // Actions
    checkApiAvailability,
    initialize,
    login,
    logout,
    loadSystemStats,
    loadUsers,
    createUser,
    updateUser,
    deleteUser,
    loadApiKeys,
    createApiKey,
    revokeApiKey,
    loadConfig,
    updateConfig,
    loadAuditLogs,
    clearCache,
    exportConfig,
  }
})

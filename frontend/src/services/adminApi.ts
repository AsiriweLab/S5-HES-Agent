/**
 * Admin API Service
 *
 * Client for the backend Admin API for user management,
 * API keys, configuration, and audit logging.
 */

const API_BASE = 'http://localhost:8000/api/admin'

// =============================================================================
// Types
// =============================================================================

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  token: string
  username: string
  role: string
  expires_at: string
}

export interface User {
  id: string
  username: string
  email: string
  role: 'admin' | 'user' | 'viewer'
  status: 'active' | 'inactive' | 'suspended'
  last_login: string | null
  created_at: string
}

export interface UserCreate {
  username: string
  email: string
  password: string
  role: 'admin' | 'user' | 'viewer'
}

export interface UserUpdate {
  email?: string
  role?: string
  status?: string
}

export interface ApiKey {
  id: string
  name: string
  key: string
  permissions: string[]
  created_at: string
  last_used: string | null
  status: 'active' | 'revoked'
}

export interface ApiKeyCreate {
  name: string
  permissions: string[]
}

export interface ConfigItem {
  key: string
  value: string | number | boolean
  type: 'string' | 'number' | 'boolean'
  category: string
  description: string
  editable: boolean
}

export interface AuditLog {
  id: string
  timestamp: string
  user: string
  action: string
  resource: string
  details: string
  ip: string
}

// S12.5: Centralized Security Audit Types
export interface SecurityAuditEvent {
  event_id: string
  timestamp: string
  category: string
  action: string
  severity: string
  description: string
  username: string | null
  user_id: string | null
  ip_address: string
  resource_type: string | null
  resource_id: string | null
  success: boolean
  error_message: string | null
  request_method: string | null
  request_path: string | null
  request_params: Record<string, unknown>
  response_status: number | null
  response_time_ms: number | null
  details: Record<string, unknown>
  correlation_id: string | null
  session_id: string | null
}

export interface SecurityAuditStats {
  total_events: number
  success_events: number
  failed_events: number
  events_by_category: Record<string, number>
  events_by_severity: Record<string, number>
  events_by_action: Record<string, number>
  recent_failures: SecurityAuditEvent[]
}

export interface SecurityAuditCategories {
  categories: string[]
  actions: string[]
  severities: string[]
}

export interface SecurityAuditLogsResponse {
  events: SecurityAuditEvent[]
  total: number
  filters: {
    category: string | null
    severity: string | null
    username: string | null
    success_only: boolean | null
  }
}

export interface SystemStats {
  uptime: string
  version: string
  python_version: string
  node_version: string
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  active_connections: number
  total_users: number
  active_api_keys: number
  audit_log_count: number
}

// =============================================================================
// Token Storage
// =============================================================================

const TOKEN_KEY = 'admin_session_token'

function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// =============================================================================
// API Client
// =============================================================================

class AdminApiService {
  private getAuthHeaders(): HeadersInit {
    const token = getStoredToken()
    if (!token) return {}
    return {
      'Authorization': `Bearer ${token}`,
    }
  }

  /**
   * Check if the admin API is available
   */
  async checkAvailability(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/overview`, {
        method: 'GET',
        headers: this.getAuthHeaders(),
        signal: AbortSignal.timeout(3000),
      })
      return response.ok
    } catch {
      return false
    }
  }

  /**
   * Check if user is currently logged in
   */
  isLoggedIn(): boolean {
    return !!getStoredToken()
  }

  /**
   * Get stored token
   */
  getToken(): string | null {
    return getStoredToken()
  }

  // =========================================================================
  // Authentication
  // =========================================================================

  /**
   * Login with username and password
   */
  async login(username: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }))
      throw new Error(error.detail || 'Login failed')
    }
    const data: LoginResponse = await response.json()
    setStoredToken(data.token)
    return data
  }

  /**
   * Logout and clear session
   */
  async logout(): Promise<void> {
    try {
      await fetch(`${API_BASE}/logout`, {
        method: 'POST',
        headers: this.getAuthHeaders(),
      })
    } catch {
      // Ignore errors on logout
    }
    clearStoredToken()
  }

  /**
   * Get current user info
   */
  async getCurrentUser(): Promise<User> {
    const response = await fetch(`${API_BASE}/me`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) {
        clearStoredToken()
        throw new Error('Session expired')
      }
      throw new Error('Failed to get user info')
    }
    return response.json()
  }

  // =========================================================================
  // System Overview
  // =========================================================================

  /**
   * Get system overview statistics
   */
  async getOverview(): Promise<SystemStats> {
    const response = await fetch(`${API_BASE}/overview`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) {
        clearStoredToken()
        throw new Error('Session expired')
      }
      throw new Error('Failed to get overview')
    }
    return response.json()
  }

  // =========================================================================
  // User Management
  // =========================================================================

  /**
   * List all users
   */
  async listUsers(): Promise<User[]> {
    const response = await fetch(`${API_BASE}/users`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) throw new Error('Session expired')
      if (response.status === 403) throw new Error('Admin access required')
      throw new Error('Failed to list users')
    }
    return response.json()
  }

  /**
   * Create a new user
   */
  async createUser(user: UserCreate): Promise<User> {
    const response = await fetch(`${API_BASE}/users`, {
      method: 'POST',
      headers: {
        ...this.getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(user),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to create user' }))
      throw new Error(error.detail || 'Failed to create user')
    }
    return response.json()
  }

  /**
   * Update a user
   */
  async updateUser(userId: string, updates: UserUpdate): Promise<User> {
    const response = await fetch(`${API_BASE}/users/${userId}`, {
      method: 'PATCH',
      headers: {
        ...this.getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update user' }))
      throw new Error(error.detail || 'Failed to update user')
    }
    return response.json()
  }

  /**
   * Delete a user
   */
  async deleteUser(userId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/users/${userId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to delete user' }))
      throw new Error(error.detail || 'Failed to delete user')
    }
  }

  // =========================================================================
  // API Key Management
  // =========================================================================

  /**
   * List all API keys
   */
  async listApiKeys(): Promise<ApiKey[]> {
    const response = await fetch(`${API_BASE}/apikeys`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) throw new Error('Session expired')
      if (response.status === 403) throw new Error('Admin access required')
      throw new Error('Failed to list API keys')
    }
    return response.json()
  }

  /**
   * Create a new API key
   */
  async createApiKey(data: ApiKeyCreate): Promise<ApiKey> {
    const response = await fetch(`${API_BASE}/apikeys`, {
      method: 'POST',
      headers: {
        ...this.getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to create API key' }))
      throw new Error(error.detail || 'Failed to create API key')
    }
    return response.json()
  }

  /**
   * Revoke an API key
   */
  async revokeApiKey(keyId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/apikeys/${keyId}/revoke`, {
      method: 'PATCH',
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to revoke API key' }))
      throw new Error(error.detail || 'Failed to revoke API key')
    }
  }

  // =========================================================================
  // Configuration Management
  // =========================================================================

  /**
   * Get all configuration items
   */
  async getConfig(): Promise<ConfigItem[]> {
    const response = await fetch(`${API_BASE}/config`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) throw new Error('Session expired')
      throw new Error('Failed to get config')
    }
    return response.json()
  }

  /**
   * Update a configuration value
   */
  async updateConfig(key: string, value: string | number | boolean): Promise<ConfigItem> {
    const response = await fetch(`${API_BASE}/config/${key}`, {
      method: 'PATCH',
      headers: {
        ...this.getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ value }),
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Failed to update config' }))
      throw new Error(error.detail || 'Failed to update config')
    }
    return response.json()
  }

  // =========================================================================
  // Audit Log
  // =========================================================================

  /**
   * Get audit logs (legacy)
   */
  async getAuditLogs(options: {
    limit?: number
    action?: string
    user?: string
  } = {}): Promise<AuditLog[]> {
    const params = new URLSearchParams()
    if (options.limit) params.set('limit', String(options.limit))
    if (options.action) params.set('action', options.action)
    if (options.user) params.set('user', options.user)

    const url = params.toString() ? `${API_BASE}/audit?${params}` : `${API_BASE}/audit`
    const response = await fetch(url, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) throw new Error('Session expired')
      if (response.status === 403) throw new Error('Admin access required')
      throw new Error('Failed to get audit logs')
    }
    return response.json()
  }

  // =========================================================================
  // Security Audit Logs (S12.5 Centralized)
  // =========================================================================

  /**
   * Get security audit logs from centralized service
   */
  async getSecurityAuditLogs(options: {
    limit?: number
    category?: string
    severity?: string
    username?: string
    success_only?: boolean
  } = {}): Promise<SecurityAuditLogsResponse> {
    const params = new URLSearchParams()
    if (options.limit) params.set('limit', String(options.limit))
    if (options.category) params.set('category', options.category)
    if (options.severity) params.set('severity', options.severity)
    if (options.username) params.set('username', options.username)
    if (options.success_only !== undefined) params.set('success_only', String(options.success_only))

    const url = params.toString() ? `${API_BASE}/security-audit?${params}` : `${API_BASE}/security-audit`
    const response = await fetch(url, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) throw new Error('Session expired')
      if (response.status === 403) throw new Error('Admin access required')
      throw new Error('Failed to get security audit logs')
    }
    return response.json()
  }

  /**
   * Get security audit statistics
   */
  async getSecurityAuditStats(): Promise<SecurityAuditStats> {
    const response = await fetch(`${API_BASE}/security-audit/stats`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) throw new Error('Session expired')
      if (response.status === 403) throw new Error('Admin access required')
      throw new Error('Failed to get security audit stats')
    }
    return response.json()
  }

  /**
   * Get available audit categories, actions, and severities
   */
  async getSecurityAuditCategories(): Promise<SecurityAuditCategories> {
    const response = await fetch(`${API_BASE}/security-audit/categories`, {
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      if (response.status === 401) throw new Error('Session expired')
      throw new Error('Failed to get security audit categories')
    }
    return response.json()
  }

  // =========================================================================
  // System Actions
  // =========================================================================

  /**
   * Clear system cache
   */
  async clearCache(): Promise<void> {
    const response = await fetch(`${API_BASE}/actions/clear-cache`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      throw new Error('Failed to clear cache')
    }
  }

  /**
   * Export configuration
   */
  async exportConfig(): Promise<{ configs: { key: string; value: unknown }[]; exported_at: string; exported_by: string }> {
    const response = await fetch(`${API_BASE}/actions/export-config`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    })
    if (!response.ok) {
      throw new Error('Failed to export config')
    }
    return response.json()
  }
}

// Export singleton instance
export const adminApi = new AdminApiService()

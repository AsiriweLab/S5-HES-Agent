<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'

// ============== STORE ==============

const adminStore = useAdminStore()

// ============== LOCAL STATE ==============

const activeSection = ref<'overview' | 'config' | 'users' | 'apikeys' | 'audit'>('overview')

// Login form
const loginUsername = ref('')
const loginPassword = ref('')
const loginError = ref('')

// Edit state
const editingConfig = ref<string | null>(null)
const editValue = ref<string | number | boolean>('')

// Modals
const showAddUserModal = ref(false)
const showAddKeyModal = ref(false)
const showNewKeyModal = ref(false)
const newKeyValue = ref('')
const newUser = ref({ username: '', email: '', password: '', role: 'user' as const })
const newApiKey = ref({ name: '', permissions: [] as string[] })

// ============== COMPUTED ==============

const isAuthenticated = computed(() => adminStore.isAuthenticated)
const currentUser = computed(() => adminStore.currentUser)
const isLoading = computed(() => adminStore.isLoading)

const systemStats = computed(() => adminStore.systemStats || {
  uptime: 'Loading...',
  version: '1.0.0-beta',
  python_version: 'Loading...',
  node_version: 'Loading...',
  cpu_usage: 0,
  memory_usage: 0,
  disk_usage: 0,
  active_connections: 0,
  total_users: 0,
  active_api_keys: 0,
  audit_log_count: 0,
})

// ============== METHODS ==============

async function handleLogin() {
  loginError.value = ''
  try {
    await adminStore.login(loginUsername.value, loginPassword.value)
  } catch (err) {
    loginError.value = err instanceof Error ? err.message : 'Login failed'
  }
}

async function handleLogout() {
  await adminStore.logout()
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  const date = new Date(dateStr)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = Date.now()
  const diff = now - date.getTime()

  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return `${Math.floor(diff / 86400000)}d ago`
}

function getRoleColor(role: string): string {
  switch (role) {
    case 'admin': return 'var(--color-danger)'
    case 'user': return 'var(--color-primary)'
    case 'viewer': return 'var(--color-success)'
    default: return 'var(--text-muted)'
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'active': return 'var(--color-success)'
    case 'inactive': return 'var(--text-muted)'
    case 'suspended': return 'var(--color-danger)'
    case 'revoked': return 'var(--color-danger)'
    default: return 'var(--text-muted)'
  }
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text)
}

function startEdit(config: { key: string; value: string | number | boolean }) {
  editingConfig.value = config.key
  editValue.value = config.value
}

async function saveEdit(config: { key: string }) {
  try {
    await adminStore.updateConfig(config.key, editValue.value)
    editingConfig.value = null
  } catch {
    // Error handled by store
  }
}

function cancelEdit() {
  editingConfig.value = null
}

async function addUser() {
  try {
    await adminStore.createUser(
      newUser.value.username,
      newUser.value.email,
      newUser.value.password,
      newUser.value.role
    )
    showAddUserModal.value = false
    newUser.value = { username: '', email: '', password: '', role: 'user' }
  } catch {
    // Error handled by store
  }
}

async function toggleUserStatus(user: { id: string; status: string }) {
  try {
    await adminStore.updateUser(user.id, {
      status: user.status === 'active' ? 'inactive' : 'active'
    })
  } catch {
    // Error handled by store
  }
}

async function addApiKey() {
  try {
    const key = await adminStore.createApiKey(
      newApiKey.value.name,
      newApiKey.value.permissions
    )
    showAddKeyModal.value = false
    newApiKey.value = { name: '', permissions: [] }
    // Show the new key to user
    newKeyValue.value = key.key
    showNewKeyModal.value = true
  } catch {
    // Error handled by store
  }
}

async function revokeApiKey(key: { id: string }) {
  try {
    await adminStore.revokeApiKey(key.id)
  } catch {
    // Error handled by store
  }
}

async function restartService() {
  alert('Service restart is not implemented in this demo.')
}

async function handleClearCache() {
  try {
    await adminStore.clearCache()
    alert('Cache cleared successfully')
  } catch {
    alert('Failed to clear cache')
  }
}

async function handleExportConfig() {
  try {
    const data = await adminStore.exportConfig()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `config-export-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    alert('Failed to export config')
  }
}

// ============== LIFECYCLE ==============

onMounted(async () => {
  await adminStore.initialize()
})
</script>

<template>
  <div class="admin-view">
    <!-- Login Screen -->
    <div v-if="!isAuthenticated" class="login-screen">
      <div class="login-card">
        <h2>Admin Login</h2>
        <p class="login-hint">Default: admin / admin123</p>

        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-group">
            <label for="username">Username</label>
            <input
              id="username"
              v-model="loginUsername"
              type="text"
              class="form-input"
              placeholder="Enter username"
              required
            />
          </div>

          <div class="form-group">
            <label for="password">Password</label>
            <input
              id="password"
              v-model="loginPassword"
              type="password"
              class="form-input"
              placeholder="Enter password"
              required
            />
          </div>

          <div v-if="loginError" class="error-message">
            {{ loginError }}
          </div>

          <button type="submit" class="btn btn-primary btn-full" :disabled="isLoading">
            {{ isLoading ? 'Logging in...' : 'Login' }}
          </button>
        </form>
      </div>
    </div>

    <!-- Admin Panel -->
    <template v-else>
      <!-- Sidebar -->
      <aside class="admin-sidebar">
        <div class="sidebar-header">
          <h2>Admin Panel</h2>
          <span class="user-badge">{{ currentUser?.username }}</span>
        </div>

        <nav class="sidebar-nav">
          <button
            class="nav-item"
            :class="{ active: activeSection === 'overview' }"
            @click="activeSection = 'overview'"
          >
            <span class="nav-icon">&#128202;</span>
            Overview
          </button>
          <button
            class="nav-item"
            :class="{ active: activeSection === 'config' }"
            @click="activeSection = 'config'"
          >
            <span class="nav-icon">&#9881;</span>
            Configuration
          </button>
          <button
            class="nav-item"
            :class="{ active: activeSection === 'users' }"
            @click="activeSection = 'users'"
          >
            <span class="nav-icon">&#128101;</span>
            Users
          </button>
          <button
            class="nav-item"
            :class="{ active: activeSection === 'apikeys' }"
            @click="activeSection = 'apikeys'"
          >
            <span class="nav-icon">&#128273;</span>
            API Keys
          </button>
          <button
            class="nav-item"
            :class="{ active: activeSection === 'audit' }"
            @click="activeSection = 'audit'"
          >
            <span class="nav-icon">&#128220;</span>
            Audit Log
          </button>
        </nav>

        <div class="sidebar-actions">
          <button class="action-btn warning" @click="handleClearCache">
            Clear Cache
          </button>
          <button class="action-btn danger" @click="restartService">
            Restart Service
          </button>
          <button class="action-btn" @click="handleLogout">
            Logout
          </button>
        </div>
      </aside>

      <!-- Main Content -->
      <main class="admin-content">
        <!-- Overview Section -->
        <section v-if="activeSection === 'overview'" class="content-section">
          <h3>System Overview</h3>

          <div class="overview-grid">
            <!-- System Info -->
            <div class="info-card">
              <h4>System Information</h4>
              <div class="info-list">
                <div class="info-item">
                  <span class="label">Version</span>
                  <span class="value">{{ systemStats.version }}</span>
                </div>
                <div class="info-item">
                  <span class="label">Uptime</span>
                  <span class="value">{{ systemStats.uptime }}</span>
                </div>
                <div class="info-item">
                  <span class="label">Python</span>
                  <span class="value">{{ systemStats.python_version }}</span>
                </div>
                <div class="info-item">
                  <span class="label">Node.js</span>
                  <span class="value">{{ systemStats.node_version }}</span>
                </div>
                <div class="info-item">
                  <span class="label">Active Connections</span>
                  <span class="value">{{ systemStats.active_connections }}</span>
                </div>
              </div>
            </div>

            <!-- Resource Usage -->
            <div class="info-card">
              <h4>Resource Usage</h4>
              <div class="resource-bars">
                <div class="resource-bar">
                  <div class="resource-header">
                    <span class="label">CPU</span>
                    <span class="value">{{ systemStats.cpu_usage }}%</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" :style="{ width: `${systemStats.cpu_usage}%`, backgroundColor: systemStats.cpu_usage > 80 ? 'var(--color-danger)' : 'var(--color-primary)' }"></div>
                  </div>
                </div>
                <div class="resource-bar">
                  <div class="resource-header">
                    <span class="label">Memory</span>
                    <span class="value">{{ systemStats.memory_usage }}%</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" :style="{ width: `${systemStats.memory_usage}%`, backgroundColor: systemStats.memory_usage > 80 ? 'var(--color-danger)' : 'var(--color-success)' }"></div>
                  </div>
                </div>
                <div class="resource-bar">
                  <div class="resource-header">
                    <span class="label">Disk</span>
                    <span class="value">{{ systemStats.disk_usage }}%</span>
                  </div>
                  <div class="bar-track">
                    <div class="bar-fill" :style="{ width: `${systemStats.disk_usage}%`, backgroundColor: systemStats.disk_usage > 80 ? 'var(--color-danger)' : 'var(--color-warning)' }"></div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Quick Stats -->
            <div class="info-card">
              <h4>Quick Stats</h4>
              <div class="quick-stats">
                <div class="stat">
                  <span class="stat-value">{{ adminStore.users.length }}</span>
                  <span class="stat-label">Users</span>
                </div>
                <div class="stat">
                  <span class="stat-value">{{ adminStore.activeApiKeys.length }}</span>
                  <span class="stat-label">Active Keys</span>
                </div>
                <div class="stat">
                  <span class="stat-value">{{ adminStore.auditLogs.length }}</span>
                  <span class="stat-label">Audit Logs</span>
                </div>
              </div>
            </div>

            <!-- Recent Activity -->
            <div class="info-card wide">
              <h4>Recent Activity</h4>
              <div class="activity-list">
                <div v-for="log in adminStore.auditLogs.slice(0, 5)" :key="log.id" class="activity-item">
                  <span class="activity-time">{{ formatRelativeTime(log.timestamp) }}</span>
                  <span class="activity-user">{{ log.user }}</span>
                  <span class="activity-action">{{ log.action }}</span>
                  <span class="activity-details">{{ log.details }}</span>
                </div>
                <div v-if="adminStore.auditLogs.length === 0" class="no-data">
                  No recent activity
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Configuration Section -->
        <section v-if="activeSection === 'config'" class="content-section">
          <div class="section-header">
            <h3>Configuration</h3>
            <button class="btn btn-primary" @click="handleExportConfig">Export Config</button>
          </div>

          <div class="config-categories">
            <div v-for="category in adminStore.configCategories" :key="category" class="config-category">
              <h4>{{ category }}</h4>
              <div class="config-list">
                <div v-for="config in adminStore.groupedConfigs[category]" :key="config.key" class="config-item">
                  <div class="config-info">
                    <span class="config-key">{{ config.key }}</span>
                    <span class="config-desc">{{ config.description }}</span>
                  </div>
                  <div class="config-value">
                    <template v-if="editingConfig === config.key">
                      <input
                        v-if="config.type === 'string' || config.type === 'number'"
                        v-model="editValue"
                        :type="config.type === 'number' ? 'number' : 'text'"
                        class="config-input"
                      />
                      <select v-else-if="config.type === 'boolean'" v-model="editValue" class="config-select">
                        <option :value="true">true</option>
                        <option :value="false">false</option>
                      </select>
                      <div class="config-actions">
                        <button class="btn btn-sm btn-primary" @click="saveEdit(config)">Save</button>
                        <button class="btn btn-sm btn-ghost" @click="cancelEdit">Cancel</button>
                      </div>
                    </template>
                    <template v-else>
                      <span class="value-display" :class="{ boolean: config.type === 'boolean' }">
                        {{ config.value }}
                      </span>
                      <button
                        v-if="config.editable"
                        class="btn btn-sm btn-ghost"
                        @click="startEdit(config)"
                      >
                        Edit
                      </button>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Users Section -->
        <section v-if="activeSection === 'users'" class="content-section">
          <div class="section-header">
            <h3>Users</h3>
            <button class="btn btn-primary" @click="showAddUserModal = true">Add User</button>
          </div>

          <div class="users-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last Login</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="user in adminStore.users" :key="user.id">
                  <td class="username">{{ user.username }}</td>
                  <td>{{ user.email }}</td>
                  <td>
                    <span class="role-badge" :style="{ backgroundColor: getRoleColor(user.role) + '20', color: getRoleColor(user.role) }">
                      {{ user.role }}
                    </span>
                  </td>
                  <td>
                    <span class="status-badge" :style="{ color: getStatusColor(user.status) }">
                      {{ user.status }}
                    </span>
                  </td>
                  <td>{{ formatDate(user.last_login) }}</td>
                  <td>{{ formatDate(user.created_at) }}</td>
                  <td>
                    <button
                      class="btn btn-sm btn-ghost"
                      @click="toggleUserStatus(user)"
                    >
                      {{ user.status === 'active' ? 'Deactivate' : 'Activate' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- API Keys Section -->
        <section v-if="activeSection === 'apikeys'" class="content-section">
          <div class="section-header">
            <h3>API Keys</h3>
            <button class="btn btn-primary" @click="showAddKeyModal = true">Create Key</button>
          </div>

          <div class="apikeys-grid">
            <div v-for="key in adminStore.apiKeys" :key="key.id" class="apikey-card" :class="key.status">
              <div class="key-header">
                <h4>{{ key.name }}</h4>
                <span class="key-status" :style="{ color: getStatusColor(key.status) }">
                  {{ key.status }}
                </span>
              </div>

              <div class="key-value">
                <code>{{ key.key }}</code>
                <button class="btn btn-sm btn-ghost" @click="copyToClipboard(key.key)">
                  Copy
                </button>
              </div>

              <div class="key-permissions">
                <span v-for="perm in key.permissions" :key="perm" class="permission-badge">
                  {{ perm }}
                </span>
              </div>

              <div class="key-meta">
                <span>Created: {{ formatDate(key.created_at) }}</span>
                <span>Last used: {{ formatDate(key.last_used) }}</span>
              </div>

              <div v-if="key.status === 'active'" class="key-actions">
                <button class="btn btn-sm btn-danger" @click="revokeApiKey(key)">
                  Revoke
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- Audit Log Section -->
        <section v-if="activeSection === 'audit'" class="content-section">
          <div class="section-header">
            <h3>Audit Log</h3>
          </div>

          <div class="audit-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Details</th>
                  <th>IP Address</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in adminStore.auditLogs" :key="log.id">
                  <td class="timestamp">{{ formatDate(log.timestamp) }}</td>
                  <td class="user">{{ log.user }}</td>
                  <td class="action">{{ log.action }}</td>
                  <td class="resource">{{ log.resource }}</td>
                  <td class="details">{{ log.details }}</td>
                  <td class="ip">{{ log.ip }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </template>

    <!-- Add User Modal -->
    <div v-if="showAddUserModal" class="modal-overlay" @click="showAddUserModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Add User</h3>
          <button class="close-btn" @click="showAddUserModal = false">&times;</button>
        </div>
        <form @submit.prevent="addUser">
          <div class="modal-body">
            <div class="form-group">
              <label for="new-username">Username</label>
              <input id="new-username" v-model="newUser.username" type="text" class="form-input" required />
            </div>
            <div class="form-group">
              <label for="new-email">Email</label>
              <input id="new-email" v-model="newUser.email" type="email" class="form-input" required />
            </div>
            <div class="form-group">
              <label for="new-password">Password</label>
              <input id="new-password" v-model="newUser.password" type="password" class="form-input" minlength="6" required />
            </div>
            <div class="form-group">
              <label for="new-role">Role</label>
              <select id="new-role" v-model="newUser.role" class="form-input">
                <option value="admin">Admin</option>
                <option value="user">User</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-ghost" @click="showAddUserModal = false">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="isLoading">Add User</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Add API Key Modal -->
    <div v-if="showAddKeyModal" class="modal-overlay" @click="showAddKeyModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Create API Key</h3>
          <button class="close-btn" @click="showAddKeyModal = false">&times;</button>
        </div>
        <form @submit.prevent="addApiKey">
          <div class="modal-body">
            <div class="form-group">
              <label for="key-name">Name</label>
              <input id="key-name" v-model="newApiKey.name" type="text" class="form-input" placeholder="e.g., Production API" required />
            </div>
            <div class="form-group">
              <label>Permissions</label>
              <div class="checkbox-group">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="newApiKey.permissions" value="read" />
                  Read
                </label>
                <label class="checkbox-label">
                  <input type="checkbox" v-model="newApiKey.permissions" value="write" />
                  Write
                </label>
                <label class="checkbox-label">
                  <input type="checkbox" v-model="newApiKey.permissions" value="admin" />
                  Admin
                </label>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-ghost" @click="showAddKeyModal = false">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="isLoading">Create Key</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Show New Key Modal -->
    <div v-if="showNewKeyModal" class="modal-overlay" @click="showNewKeyModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>API Key Created</h3>
          <button class="close-btn" @click="showNewKeyModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <p class="warning-text">Copy this key now. You won't be able to see it again!</p>
          <div class="key-display">
            <code>{{ newKeyValue }}</code>
            <button class="btn btn-sm btn-ghost" @click="copyToClipboard(newKeyValue)">
              Copy
            </button>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" @click="showNewKeyModal = false">Done</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-view {
  display: flex;
  height: calc(100vh - 60px);
  overflow: hidden;
}

/* Login Screen */
.login-screen {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-dark);
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: var(--spacing-xl);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.login-card h2 {
  margin: 0 0 var(--spacing-xs);
  text-align: center;
}

.login-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-bottom: var(--spacing-lg);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.btn-full {
  width: 100%;
}

.error-message {
  padding: var(--spacing-sm);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-sm);
  color: var(--color-danger);
  font-size: 0.85rem;
}

/* Sidebar */
.admin-sidebar {
  width: 250px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.user-badge {
  padding: 2px 8px;
  background: var(--bg-input);
  border-radius: var(--radius-full);
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.sidebar-nav {
  flex: 1;
  padding: var(--spacing-sm);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: transparent;
  border: none;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.9rem;
  text-align: left;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--color-primary);
  color: white;
}

.nav-icon {
  font-size: 1.1rem;
}

.sidebar-actions {
  padding: var(--spacing-md);
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.action-btn {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--bg-hover);
}

.action-btn.warning:hover {
  background: rgba(234, 179, 8, 0.1);
  border-color: var(--color-warning);
  color: var(--color-warning);
}

.action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--color-danger);
  color: var(--color-danger);
}

/* Main Content */
.admin-content {
  flex: 1;
  overflow: auto;
  padding: var(--spacing-lg);
}

.content-section h3 {
  margin: 0 0 var(--spacing-lg);
  font-size: 1.25rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.section-header h3 {
  margin: 0;
}

/* Overview */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-md);
}

.info-card {
  padding: var(--spacing-md);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.info-card.wide {
  grid-column: span 3;
}

.info-card h4 {
  margin: 0 0 var(--spacing-md);
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.info-item {
  display: flex;
  justify-content: space-between;
}

.info-item .label {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.info-item .value {
  font-weight: 600;
  font-size: 0.85rem;
}

.resource-bars {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.resource-bar .resource-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-xs);
  font-size: 0.8rem;
}

.bar-track {
  height: 8px;
  background: var(--bg-input);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}

.quick-stats {
  display: flex;
  justify-content: space-around;
  text-align: center;
}

.stat .stat-value {
  display: block;
  font-size: 2rem;
  font-weight: 700;
}

.stat .stat-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.activity-item {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
}

.activity-time {
  color: var(--text-muted);
  width: 80px;
  flex-shrink: 0;
}

.activity-user {
  font-weight: 600;
  width: 80px;
  flex-shrink: 0;
}

.activity-action {
  color: var(--color-primary);
  width: 120px;
  flex-shrink: 0;
}

.activity-details {
  color: var(--text-secondary);
  flex: 1;
}

.no-data {
  color: var(--text-muted);
  font-style: italic;
  text-align: center;
  padding: var(--spacing-md);
}

/* Configuration */
.config-categories {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.config-category h4 {
  margin: 0 0 var(--spacing-sm);
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.config-list {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.config-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.config-item:last-child {
  border-bottom: none;
}

.config-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.config-key {
  font-family: monospace;
  font-size: 0.85rem;
  font-weight: 500;
}

.config-desc {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.config-value {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.value-display {
  font-family: monospace;
  font-size: 0.9rem;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.value-display.boolean {
  color: var(--color-primary);
}

.config-input, .config-select {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  color: var(--text-primary);
}

.config-actions {
  display: flex;
  gap: var(--spacing-xs);
}

/* Data Tables */
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.data-table th,
.data-table td {
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.data-table th {
  background: var(--bg-input);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.data-table .timestamp,
.data-table .ip {
  font-family: monospace;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.data-table .username,
.data-table .user {
  font-weight: 600;
}

.role-badge, .status-badge {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

/* API Keys */
.apikeys-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--spacing-md);
}

.apikey-card {
  padding: var(--spacing-md);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.apikey-card.revoked {
  opacity: 0.6;
}

.key-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.key-header h4 {
  margin: 0;
  font-size: 1rem;
}

.key-status {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.key-value {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.key-value code {
  flex: 1;
  font-size: 0.85rem;
  word-break: break-all;
}

.key-permissions {
  display: flex;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-md);
}

.permission-badge {
  padding: 2px 8px;
  background: var(--bg-input);
  border-radius: var(--radius-sm);
  font-size: 0.7rem;
  text-transform: uppercase;
}

.key-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: var(--spacing-md);
}

.key-actions {
  display: flex;
  justify-content: flex-end;
}

/* Modals */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  width: 90%;
  max-width: 400px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--text-muted);
  cursor: pointer;
}

.modal-body {
  padding: var(--spacing-md);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: var(--spacing-md);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.form-input {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 0.9rem;
  color: var(--text-primary);
}

.checkbox-group {
  display: flex;
  gap: var(--spacing-md);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 0.9rem;
}

.warning-text {
  color: var(--color-warning);
  font-size: 0.85rem;
  margin-bottom: var(--spacing-md);
}

.key-display {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-sm);
}

.key-display code {
  flex: 1;
  font-size: 0.85rem;
  word-break: break-all;
}

/* Responsive */
@media (max-width: 1200px) {
  .overview-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .info-card.wide {
    grid-column: span 2;
  }
}

@media (max-width: 768px) {
  .admin-view {
    flex-direction: column;
  }

  .admin-sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .sidebar-nav {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-xs);
  }

  .sidebar-actions {
    flex-direction: row;
  }

  .overview-grid {
    grid-template-columns: 1fr;
  }

  .info-card.wide {
    grid-column: span 1;
  }

  .activity-item {
    flex-wrap: wrap;
  }

  .activity-time,
  .activity-user,
  .activity-action {
    width: auto;
  }
}
</style>

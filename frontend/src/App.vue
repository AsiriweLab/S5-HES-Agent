<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterView, RouterLink } from 'vue-router'
import { useThemeStore } from './stores/theme'
import { useChatStore } from './stores/chat'
import { useModeStore } from './stores/mode'
import { useSettingsStore } from './stores/settings'
import ModeController from './components/ModeController.vue'
import ModeIndicator from './components/ModeIndicator.vue'
import AskExpertButton from './components/AskExpertButton.vue'
import ConsultationDialog from './components/ConsultationDialog.vue'

const themeStore = useThemeStore()
const chatStore = useChatStore()
const modeStore = useModeStore()
const settingsStore = useSettingsStore()

const mobileMenuOpen = ref(false)
const buildersMenuOpen = ref(false)

function closeBuildersMenu() {
  buildersMenuOpen.value = false
}

onMounted(() => {
  themeStore.initialize()
  themeStore.setupSystemListener()
  modeStore.initialize()
  settingsStore.initialize() // Load settings from localStorage at app startup
  chatStore.fetchHealth()
})

function toggleMobileMenu() {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

function closeMobileMenu() {
  mobileMenuOpen.value = false
}
</script>

<template>
  <div class="app">
    <header class="app-header">
      <div class="header-left">
        <button
          class="mobile-menu-btn hide-desktop"
          @click="toggleMobileMenu"
          :aria-label="mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'"
          :title="mobileMenuOpen ? 'Close menu' : 'Open menu'"
        >
          <svg v-if="!mobileMenuOpen" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
          <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
        <router-link to="/" class="logo">
          <span class="logo-icon">&#9889;</span>
          <span class="logo-text">S5-HES Agent</span>
        </router-link>
        <ModeIndicator class="hide-mobile" />
      </div>

      <nav class="app-nav hide-mobile" :class="{ 'mobile-open': mobileMenuOpen }">
        <router-link to="/" @click="closeMobileMenu">Dashboard</router-link>
        <router-link to="/chat" @click="closeMobileMenu">
          AI Chat
          <span class="status-dot" :class="chatStore.isHealthy ? 'online' : 'offline'"></span>
        </router-link>
        <div class="nav-dropdown" @mouseenter="buildersMenuOpen = true" @mouseleave="closeBuildersMenu">
          <button class="nav-dropdown-trigger" :class="{ active: $route.path.includes('builder') }">
            Builders
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          <div v-if="buildersMenuOpen" class="nav-dropdown-menu">
            <router-link to="/home-builder" @click="closeBuildersMenu">
              <span class="dropdown-icon">🏠</span>
              Home Builder
            </router-link>
            <router-link to="/threat-builder" @click="closeBuildersMenu">
              <span class="dropdown-icon">🎯</span>
              Threat Builder
            </router-link>
          </div>
        </div>
        <router-link to="/agents" @click="closeMobileMenu">Agents</router-link>
        <router-link to="/knowledge-base" @click="closeMobileMenu">Knowledge</router-link>
        <router-link to="/simulation" @click="closeMobileMenu">Simulation</router-link>
        <router-link to="/monitoring" @click="closeMobileMenu">Monitor</router-link>
        <router-link to="/history" @click="closeMobileMenu">History</router-link>
        <router-link to="/experiments" @click="closeMobileMenu">Experiments</router-link>
        <router-link to="/parameter-sweep" @click="closeMobileMenu">Sweep</router-link>
        <router-link to="/admin" @click="closeMobileMenu">Admin</router-link>
        <router-link to="/settings" @click="closeMobileMenu">Settings</router-link>
      </nav>

      <div class="header-right">
        <AskExpertButton v-if="modeStore.isNoLLMMode" class="hide-mobile" />
        <ModeController class="hide-mobile" />
        <button class="theme-toggle btn btn-ghost btn-icon" @click="themeStore.toggle" :title="themeStore.isDark ? 'Switch to light mode' : 'Switch to dark mode'">
          <svg v-if="themeStore.isDark" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"></circle>
            <line x1="12" y1="1" x2="12" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="23"></line>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
            <line x1="1" y1="12" x2="3" y2="12"></line>
            <line x1="21" y1="12" x2="23" y2="12"></line>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
          </svg>
        </button>
      </div>
    </header>

    <!-- Mobile Navigation Overlay -->
    <div v-if="mobileMenuOpen" class="mobile-nav-overlay hide-desktop" @click="closeMobileMenu">
      <nav class="mobile-nav" @click.stop>
        <div class="mobile-mode-section">
          <ModeIndicator />
          <ModeController />
        </div>
        <router-link to="/" @click="closeMobileMenu">
          <span>Dashboard</span>
        </router-link>
        <router-link to="/chat" @click="closeMobileMenu">
          <span>AI Chat</span>
          <span class="status-dot" :class="chatStore.isHealthy ? 'online' : 'offline'"></span>
        </router-link>
        <router-link to="/home-builder" @click="closeMobileMenu">
          <span>Home Builder</span>
        </router-link>
        <router-link to="/threat-builder" @click="closeMobileMenu">
          <span>Threat Builder</span>
        </router-link>
        <router-link to="/agents" @click="closeMobileMenu">
          <span>Agents</span>
        </router-link>
        <router-link to="/knowledge-base" @click="closeMobileMenu">
          <span>Knowledge Base</span>
        </router-link>
        <router-link to="/simulation" @click="closeMobileMenu">
          <span>Simulation</span>
        </router-link>
        <router-link to="/monitoring" @click="closeMobileMenu">
          <span>Monitoring</span>
        </router-link>
        <router-link to="/history" @click="closeMobileMenu">
          <span>History</span>
        </router-link>
        <router-link to="/experiments" @click="closeMobileMenu">
          <span>Experiments</span>
        </router-link>
        <router-link to="/parameter-sweep" @click="closeMobileMenu">
          <span>Sweep</span>
        </router-link>
        <router-link to="/admin" @click="closeMobileMenu">
          <span>Admin</span>
        </router-link>
        <router-link to="/settings" @click="closeMobileMenu">
          <span>Settings</span>
        </router-link>
        <div v-if="modeStore.isNoLLMMode" class="mobile-expert-section">
          <AskExpertButton />
        </div>
      </nav>
    </div>

    <main class="app-main">
      <RouterView />
    </main>

    <footer class="app-footer">
      <p>S5-HES Agent v0.1.0 | Research-Grade IoT Simulation</p>
    </footer>

    <!-- Global Consultation Dialog -->
    <ConsultationDialog />
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  padding: var(--spacing-md) var(--spacing-lg);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
  transition: background-color var(--transition-normal), border-color var(--transition-normal);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.mobile-menu-btn {
  background: transparent;
  border: none;
  color: var(--text-primary);
  padding: var(--spacing-xs);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  text-decoration: none;
  color: var(--text-primary);
  font-weight: 600;
  font-size: 1.25rem;
}

.logo:hover {
  text-decoration: none;
}

.logo-icon {
  font-size: 1.5rem;
}

.logo-text {
  color: var(--color-primary);
}

.app-nav {
  display: flex;
  gap: var(--spacing-lg);
}

.app-nav a {
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background-color var(--transition-fast);
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.app-nav a:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
  text-decoration: none;
}

.app-nav a.router-link-active {
  color: var(--color-primary);
}

/* Dropdown Menu */
.nav-dropdown {
  position: relative;
}

.nav-dropdown-trigger {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  color: var(--text-secondary);
  background: transparent;
  border: none;
  font-weight: 500;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color var(--transition-fast), background-color var(--transition-fast);
}

.nav-dropdown-trigger:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.nav-dropdown-trigger.active {
  color: var(--color-primary);
}

.nav-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-xs);
  min-width: 180px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 200;
  animation: dropdownFadeIn 0.15s ease;
}

@keyframes dropdownFadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.nav-dropdown-menu a {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.nav-dropdown-menu a:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-dropdown-menu a.router-link-active {
  color: var(--color-primary);
  background: var(--bg-hover);
}

.dropdown-icon {
  font-size: 1rem;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.theme-toggle {
  color: var(--text-secondary);
}

.theme-toggle:hover {
  color: var(--color-primary);
}

/* Mobile Navigation */
.mobile-nav-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
  animation: fadeIn var(--transition-fast);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.mobile-nav {
  position: absolute;
  top: 60px;
  left: 0;
  right: 0;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  animation: slideDown var(--transition-normal);
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.mobile-mode-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm);
  background: var(--bg-input);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-sm);
}

.mobile-expert-section {
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
  margin-top: var(--spacing-sm);
}

.mobile-nav a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  border-radius: var(--radius-sm);
  transition: background-color var(--transition-fast), color var(--transition-fast);
}

.mobile-nav a:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.mobile-nav a.router-link-active {
  color: var(--color-primary);
  background: var(--bg-hover);
}

.app-main {
  flex: 1;
  padding: var(--spacing-xl);
  background: var(--bg-dark);
  transition: background-color var(--transition-normal);
}

.app-footer {
  background: var(--bg-card);
  border-top: 1px solid var(--border-color);
  color: var(--text-muted);
  text-align: center;
  padding: var(--spacing-md);
  font-size: 0.875rem;
  transition: background-color var(--transition-normal), border-color var(--transition-normal);
}

@media (max-width: 768px) {
  .app-header {
    padding: var(--spacing-sm) var(--spacing-md);
  }

  .app-main {
    padding: var(--spacing-md);
  }

  .logo-text {
    font-size: 1rem;
  }
}
</style>

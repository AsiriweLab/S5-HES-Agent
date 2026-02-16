import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/ChatView.vue'),
  },
  {
    path: '/home-builder',
    name: 'HomeBuilder',
    component: () => import('@/views/HomeBuilderView.vue'),
  },
  {
    path: '/threat-builder',
    name: 'ThreatBuilder',
    component: () => import('@/views/ThreatBuilderView.vue'),
  },
  {
    path: '/agents',
    name: 'AgentDashboard',
    component: () => import('@/views/AgentDashboardView.vue'),
  },
  {
    path: '/knowledge-base',
    name: 'KnowledgeBase',
    component: () => import('@/views/KnowledgeBaseView.vue'),
  },
  {
    path: '/simulation',
    name: 'Simulation',
    component: () => import('@/views/SimulationView.vue'),
  },
  {
    path: '/monitoring',
    name: 'Monitoring',
    component: () => import('@/views/MonitoringView.vue'),
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/HistoryView.vue'),
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/views/AdminView.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
  },
  {
    path: '/experiments',
    name: 'Experiments',
    component: () => import('@/views/ExperimentsView.vue'),
  },
  {
    path: '/parameter-sweep',
    name: 'ParameterSweep',
    component: () => import('@/views/ParameterSweepView.vue'),
  },
  {
    path: '/export',
    name: 'Export',
    component: () => import('@/views/ExportView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router

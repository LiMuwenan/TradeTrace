import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from './components/LandingPage.vue'
import Dashboard from './components/Dashboard.vue'
import AlertsPage from './components/AlertsPage.vue'
import AlertDetailPage from './components/AlertDetailPage.vue'
import NotificationSettingsPage from './components/NotificationSettingsPage.vue'
import RulesPage from './components/RulesPage.vue'

/**
 * 路由而不是 ref 切 view：预警详情需要能刷新保持、能直接开链接（07 票备注）。
 */
const routes = [
  { path: '/', name: 'landing', component: LandingPage },
  { path: '/dashboard', name: 'dashboard', component: Dashboard },
  { path: '/alerts', name: 'alerts', component: AlertsPage },
  { path: '/alerts/:id(\\d+)', name: 'alert-detail', component: AlertDetailPage, props: true },
  { path: '/rules', name: 'rules', component: RulesPage },
  { path: '/settings/notification', name: 'notification-settings', component: NotificationSettingsPage },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

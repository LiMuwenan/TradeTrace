import { createRouter, createWebHistory } from 'vue-router'
import LandingPage from './components/LandingPage.vue'
import Dashboard from './components/Dashboard.vue'
import AlertsPage from './components/AlertsPage.vue'
import AlertDetailPage from './components/AlertDetailPage.vue'
import NotificationSettingsPage from './components/NotificationSettingsPage.vue'
import RulesPage from './components/RulesPage.vue'
import ReportsPage from './components/ReportsPage.vue'
import ReportDetailPage from './components/ReportDetailPage.vue'
import PipelineRunsPage from './components/PipelineRunsPage.vue'

// 图表库体积大，详情页按需加载，不拖慢首屏
const StockDetailPage = () => import('./components/StockDetailPage.vue')

/**
 * 路由而不是 ref 切 view：预警详情需要能刷新保持、能直接开链接（07 票备注）。
 */
const routes = [
  { path: '/', name: 'landing', component: LandingPage },
  { path: '/dashboard', name: 'dashboard', component: Dashboard },
  { path: '/alerts', name: 'alerts', component: AlertsPage },
  { path: '/alerts/:id(\\d+)', name: 'alert-detail', component: AlertDetailPage, props: true },
  { path: '/rules', name: 'rules', component: RulesPage },
  { path: '/stocks/:code', name: 'stock-detail', component: StockDetailPage, props: true },
  { path: '/reports', name: 'reports', component: ReportsPage },
  { path: '/reports/:date(\\d{4}-\\d{2}-\\d{2})', name: 'report-detail', component: ReportDetailPage, props: true },
  { path: '/pipeline', name: 'pipeline', component: PipelineRunsPage },
  { path: '/settings/notification', name: 'notification-settings', component: NotificationSettingsPage },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    // 控制台内的分区锚点（#health / #watchlist / #data-status）：滚到对应卡片，留出 sticky 顶栏
    if (to.hash) return { el: to.hash, top: 72, behavior: 'smooth' }
    return { top: 0 }
  },
})

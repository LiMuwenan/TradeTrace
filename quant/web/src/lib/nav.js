/**
 * 侧栏导航的唯一来源。
 *
 * 页面分两类：真正独立的路由页（`/rules`、`/alerts` …）与会落在控制台里的分区（服务状态、
 * 自选、数据状态）。两类混在同一张表里，任何页面看到的侧栏才是同一套——之前控制台与
 * AppShell 各写一份，结果这三个分区只在控制台出现，一进其他页就消失。
 */
import {
  Activity, Bell, Database, FileText, Home, LayoutDashboard, ListFilter, RefreshCw, Settings2, Star,
} from 'lucide-vue-next'

export const NAV_GROUPS = [
  {
    label: '工作区',
    items: [
      { label: '控制台', icon: LayoutDashboard, to: '/dashboard' },
      { label: '服务状态', icon: Activity, section: 'health' },
      { label: '自选', icon: Star, section: 'watchlist' },
      { label: '数据状态', icon: Database, section: 'data-status' },
      { label: '运行记录', icon: RefreshCw, to: '/pipeline' },
    ],
  },
  {
    label: '预警与规则',
    items: [
      { label: '规则', icon: ListFilter, to: '/rules' },
      { label: '预警列表', icon: Bell, to: '/alerts', badge: true },
      { label: '日报', icon: FileText, to: '/reports' },
      { label: '通知设置', icon: Settings2, to: '/settings/notification' },
    ],
  },
  {
    label: '资源',
    items: [{ label: '返回首页', icon: Home, to: '/', leave: true }],
  },
]

/** 分区锚点与路由页统一成可跳转的目标。 */
export function navHref(item) {
  return item.section ? `/dashboard#${item.section}` : item.to
}

const PREFIX_MATCHED = ['/settings/notification', '/alerts', '/reports']

/**
 * 当前条目是否高亮：分区条目只在控制台且停在该分区时高亮，路由页按前缀匹配详情页。
 */
export function isNavActive(item, path, activeSection) {
  if (item.section) return path === '/dashboard' && activeSection === item.section
  if (item.to === '/dashboard') return path === '/dashboard' && !activeSection
  if (item.to === '/') return path === '/'
  if (PREFIX_MATCHED.includes(item.to)) return path === item.to || path.startsWith(`${item.to}/`)
  return path === item.to
}

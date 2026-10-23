import { router } from 'expo-router'

/** Web 直接打开详情页时没有历史栈，回退到首页兜底 */
export function goBack() {
  if (router.canGoBack()) {
    router.back()
    return
  }
  router.replace('/')
}

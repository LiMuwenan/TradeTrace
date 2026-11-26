import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** shadcn 风格的 class 合并：条件类名 + Tailwind 冲突消解 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

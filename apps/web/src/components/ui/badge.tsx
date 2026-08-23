import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type BadgeVariant = 'default' | 'outline' | 'success' | 'warning' | 'destructive' | 'accent'

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-muted text-foreground',
  outline: 'border border-border bg-transparent text-foreground',
  success: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  warning: 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  destructive: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
  accent: 'bg-accent text-accent-foreground',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  )
}
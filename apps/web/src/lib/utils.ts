import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return 'Not available'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Not available'
  return d.toLocaleString()
}

export function formatRole(role: string): string {
  return role.charAt(0).toUpperCase() + role.slice(1)
}

export function shortId(id: string): string {
  return id.slice(0, 8)
}
export function formatValue(value: Record<string, unknown>): string {
  const entries = Object.entries(value)
  if (entries.length === 0) return '{}'
  if (entries.length === 1) {
    const [key, val] = entries[0]
    return `${key}=${String(val)}`
  }
  return JSON.stringify(value)
}

export function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
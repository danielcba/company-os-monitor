import { describe, it, expect } from 'vitest'
import { formatDateTime, formatRole, shortId } from '@/lib/utils'

describe('formatDateTime', () => {
  it('formats a valid ISO string', () => {
    const result = formatDateTime('2026-08-15T10:30:00Z')
    expect(result).not.toBe('Not available')
    expect(result).toContain('2026')
  })

  it('returns "Not available" for null', () => {
    expect(formatDateTime(null)).toBe('Not available')
  })

  it('returns "Not available" for undefined', () => {
    expect(formatDateTime(undefined)).toBe('Not available')
  })

  it('returns "Not available" for an invalid date string', () => {
    expect(formatDateTime('not-a-date')).toBe('Not available')
  })

  it('returns "Not available" for empty string', () => {
    expect(formatDateTime('')).toBe('Not available')
  })
})

describe('formatRole', () => {
  it('capitalizes the first letter', () => {
    expect(formatRole('viewer')).toBe('Viewer')
    expect(formatRole('admin')).toBe('Admin')
    expect(formatRole('superadmin')).toBe('Superadmin')
    expect(formatRole('operator')).toBe('Operator')
  })

  it('handles single-character strings', () => {
    expect(formatRole('a')).toBe('A')
  })
})

describe('shortId', () => {
  it('returns the first 8 characters', () => {
    expect(shortId('00000000-0000-0000-0000-000000000001')).toBe('00000000')
  })

  it('returns the full string if shorter than 8', () => {
    expect(shortId('abc')).toBe('abc')
  })

  it('returns exactly 8 chars for an 8-char string', () => {
    expect(shortId('12345678')).toBe('12345678')
  })
})

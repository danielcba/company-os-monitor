import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QualityClassBadge, QualityClassLegend } from '@/components/cognitive/QualityClassBadge'
import { QUALITY_CLASS_LABELS, QUALITY_CLASS_ORDER } from '@/lib/quality-class'
import type { QualityClass } from '@/types/cognitive'

describe('QUALITY_CLASS_LABELS', () => {
  it('maps Q1 to Direct Measurement', () => {
    expect(QUALITY_CLASS_LABELS.Q1).toBe('Direct Measurement')
  })

  it('maps Q2 to Corroborated Inference', () => {
    expect(QUALITY_CLASS_LABELS.Q2).toBe('Corroborated Inference')
  })

  it('maps Q3 to Statistical Regularity', () => {
    expect(QUALITY_CLASS_LABELS.Q3).toBe('Statistical Regularity')
  })

  it('maps Q4 to Anecdotal / Single-Source', () => {
    expect(QUALITY_CLASS_LABELS.Q4).toBe('Anecdotal / Single-Source')
  })

  it('has exactly 4 entries', () => {
    expect(Object.keys(QUALITY_CLASS_LABELS)).toHaveLength(4)
  })
})

describe('QUALITY_CLASS_ORDER', () => {
  it('orders from Q1 to Q4', () => {
    expect(QUALITY_CLASS_ORDER).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  it('has exactly 4 entries', () => {
    expect(QUALITY_CLASS_ORDER).toHaveLength(4)
  })
})

describe('QualityClassBadge', () => {
  const classes: QualityClass[] = ['Q1', 'Q2', 'Q3', 'Q4']

  it.each(classes)('renders badge with label for %s', (qc) => {
    render(<QualityClassBadge qualityClass={qc} />)
    expect(screen.getByText(qc)).toBeInTheDocument()
  })

  it('includes the full label in the title attribute', () => {
    render(<QualityClassBadge qualityClass="Q1" />)
    const badge = screen.getByText('Q1')
    expect(badge.closest('[title]')).toHaveAttribute(
      'title',
      `Q1 — ${QUALITY_CLASS_LABELS.Q1}`,
    )
  })

  it('renders with outline variant', () => {
    render(<QualityClassBadge qualityClass="Q2" />)
    const badge = screen.getByText('Q2')
    expect(badge).toHaveClass('border')
  })

  it('applies Q1 emerald color classes', () => {
    render(<QualityClassBadge qualityClass="Q1" />)
    const badge = screen.getByText('Q1')
    expect(badge.className).toContain('emerald')
  })

  it('applies Q3 amber color classes', () => {
    render(<QualityClassBadge qualityClass="Q3" />)
    const badge = screen.getByText('Q3')
    expect(badge.className).toContain('amber')
  })

  it('applies Q4 red color classes', () => {
    render(<QualityClassBadge qualityClass="Q4" />)
    const badge = screen.getByText('Q4')
    expect(badge.className).toContain('red')
  })
})

describe('QualityClassLegend', () => {
  it('renders all four quality class entries', () => {
    render(<QualityClassLegend />)
    expect(screen.getByText(/Q1 — Direct Measurement/)).toBeInTheDocument()
    expect(screen.getByText(/Q2 — Corroborated Inference/)).toBeInTheDocument()
    expect(screen.getByText(/Q3 — Statistical Regularity/)).toBeInTheDocument()
    expect(screen.getByText(/Q4 — Anecdotal \/ Single-Source/)).toBeInTheDocument()
  })

  it('renders exactly 4 legend items', () => {
    render(<QualityClassLegend />)
    const items = screen.getAllByText(/^Q[1-4]/)
    expect(items).toHaveLength(4)
  })
})

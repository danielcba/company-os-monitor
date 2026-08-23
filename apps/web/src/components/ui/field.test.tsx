import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Field } from './field'

describe('Field', () => {
  it('renders label and value', () => {
    render(<Field label="Status" value="Active" />)
    expect(screen.getByText('Status')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('renders with React node value', () => {
    render(<Field label="Score" value={<span data-testid="score">0.85</span>} />)
    expect(screen.getByTestId('score')).toHaveTextContent('0.85')
  })

  it('applies uppercase styling to label', () => {
    render(<Field label="Type" value="cpu" />)
    const label = screen.getByText('Type')
    expect(label.className).toContain('uppercase')
  })
})

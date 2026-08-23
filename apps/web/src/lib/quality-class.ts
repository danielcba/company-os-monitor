import type { QualityClass } from '@/types/cognitive'

export const QUALITY_CLASS_LABELS: Record<QualityClass, string> = {
  Q1: 'Direct Measurement',
  Q2: 'Corroborated Inference',
  Q3: 'Statistical Regularity',
  Q4: 'Anecdotal / Single-Source',
}

export const QUALITY_CLASS_ORDER: QualityClass[] = ['Q1', 'Q2', 'Q3', 'Q4']
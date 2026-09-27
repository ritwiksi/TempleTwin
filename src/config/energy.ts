import type { EnergyState } from '../types/energy'

export function getLoadZScore(
  currentIntensityWPerFt2: number,
  baselineProfile: EnergyState[],
): number {
  const values = baselineProfile
    .map((row) => row.energy_intensity_w_ft2)
    .filter(Number.isFinite)

  if (values.length < 2) return 0

  const mean = values.reduce((sum, value) => sum + value, 0) / values.length
  const variance =
    values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length
  const standardDeviation = Math.sqrt(variance)

  if (standardDeviation < 1e-9) return 0
  return (currentIntensityWPerFt2 - mean) / standardDeviation
}

export function getLoadAnomalyColor(zScore: number): string {
  if (zScore >= 3) return '#ef4444'
  if (zScore >= 2) return '#f59e0b'
  if (zScore >= 1) return '#eab308'
  return '#22c55e'
}

export function getLoadAnomalyStatusColor(zScore: number): string {
  if (zScore >= 3) return '#d56565'
  if (zScore >= 2) return '#cf8a58'
  if (zScore >= 1) return '#d2b25e'
  return '#6fbd87'
}

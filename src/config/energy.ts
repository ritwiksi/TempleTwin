export const ENERGY_INTENSITY_THRESHOLDS = {
  moderate: 1.75,
  high: 2.75,
  veryHigh: 3.75,
} as const

export function getEnergyIntensityColor(intensityWPerFt2: number): string {
  if (intensityWPerFt2 >= ENERGY_INTENSITY_THRESHOLDS.veryHigh) return '#ef4444'
  if (intensityWPerFt2 >= ENERGY_INTENSITY_THRESHOLDS.high) return '#f59e0b'
  if (intensityWPerFt2 >= ENERGY_INTENSITY_THRESHOLDS.moderate) return '#eab308'
  return '#22c55e'
}

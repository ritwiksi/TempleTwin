export type EnergyThresholds = {
  moderate: number
  high: number
  veryHigh: number
}

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0
  const index = (sorted.length - 1) * q
  const lower = Math.floor(index)
  const upper = Math.ceil(index)
  if (lower === upper) return sorted[lower]
  const weight = index - lower
  return sorted[lower] * (1 - weight) + sorted[upper] * weight
}

export function deriveEnergyIntensityThresholds(values: number[]): EnergyThresholds {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b)
  return {
    moderate: quantile(sorted, 0.25),
    high: quantile(sorted, 0.5),
    veryHigh: quantile(sorted, 0.75),
  }
}

export function getEnergyIntensityColor(
  intensityWPerFt2: number,
  thresholds: EnergyThresholds,
): string {
  if (intensityWPerFt2 >= thresholds.veryHigh) return '#ef4444'
  if (intensityWPerFt2 >= thresholds.high) return '#f59e0b'
  if (intensityWPerFt2 >= thresholds.moderate) return '#eab308'
  return '#22c55e'
}

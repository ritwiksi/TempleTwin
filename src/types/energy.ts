export type BuildingSlug = 'serc' | 'beury' | 'engineering'

export type HourlyState = {
  timestamp: string
  hour: number
  hvac_kw: number
  lighting_kw: number
  process_kw: number
  other_kw: number
  demand_kw: number
  solar_kw: number
  grid_import_kw: number
  energy_intensity_w_ft2: number
  carbon_kg: number | null
}

export type BuildingProfileMap = Record<BuildingSlug, HourlyState[]>

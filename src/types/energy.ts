export type BuildingSlug = 'serc' | 'beury' | 'engineering'

export type EnergyState = {
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

export type BuildingProfileMap = Record<BuildingSlug, EnergyState[]>


export type WeatherHour = {
  timestamp: string
  temperature_f: number
  relative_humidity_pct: number
  cloud_cover_pct: number
  ghi_w_m2: number
  dni_w_m2: number
  weather_code: number
  source: string
}


export type BuildingMetadata = {
  id: number
  slug: BuildingSlug
  name: string
  floor_area_ft2: number
  latitude: number
  longitude: number
  approx_height_m: number
  building_type: string
  area_source: string
  area_is_estimated: boolean
  modeled_annual_eui_kwh_ft2: number
  model_notes: string
}

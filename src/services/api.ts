import type {
  BuildingMetadata,
  BuildingProfileMap,
  BuildingSlug,
  EnergyState,
  InterventionFlags,
  WeatherHour,
} from '../types/energy'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')

export async function fetchAllProfiles(): Promise<BuildingProfileMap> {
  const response = await fetch(`${API_BASE_URL}/api/profiles`)
  if (!response.ok) {
    throw new Error(`Profiles request failed: ${response.status}`)
  }

  const profiles = (await response.json()) as BuildingProfileMap
  for (const [slug, rows] of Object.entries(profiles)) {
    if (rows.length !== 96) {
      throw new Error(
        `Expected 96 15-minute rows for ${slug}, received ${rows.length}`,
      )
    }
    profiles[slug] = [...rows].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
    )
  }
  return profiles
}

export async function fetchWeather(): Promise<WeatherHour[]> {
  const response = await fetch(`${API_BASE_URL}/api/weather`)
  if (!response.ok) {
    throw new Error(`Weather request failed: ${response.status}`)
  }
  const rows = (await response.json()) as WeatherHour[]
  if (rows.length !== 24) {
    throw new Error(`Expected 24 cached weather rows, received ${rows.length}`)
  }
  return rows
}

export async function fetchBuildings(): Promise<BuildingMetadata[]> {
  const response = await fetch(`${API_BASE_URL}/api/buildings`)
  if (!response.ok) {
    throw new Error(`Buildings request failed: ${response.status}`)
  }
  return (await response.json()) as BuildingMetadata[]
}

export async function simulateInterventions(
  slug: BuildingSlug,
  interventions: InterventionFlags,
): Promise<EnergyState[]> {
  const response = await fetch(`${API_BASE_URL}/api/buildings/${slug}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(interventions),
  })

  if (!response.ok) {
    throw new Error(`Simulation request failed for ${slug}: ${response.status}`)
  }

  const rows = (await response.json()) as EnergyState[]
  if (rows.length !== 96) {
    throw new Error(`Expected 96 simulated rows for ${slug}, received ${rows.length}`)
  }
  return rows
}

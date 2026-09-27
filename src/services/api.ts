import type {
  BuildingMetadata,
  BuildingProfileMap,
  BuildingSlug,
  EnergyState,
  InterventionFlags,
  SimulationConfig,
  WeatherHour,
} from '../types/energy'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')

export async function fetchSimulationConfig(): Promise<SimulationConfig> {
  const response = await fetch(`${API_BASE_URL}/api/simulation`)
  if (!response.ok) {
    throw new Error(`Simulation request failed: ${response.status}`)
  }
  return (await response.json()) as SimulationConfig
}

export async function fetchAllProfiles(date: string): Promise<BuildingProfileMap> {
  const response = await fetch(`${API_BASE_URL}/api/profiles?date=${encodeURIComponent(date)}`)
  if (!response.ok) {
    throw new Error(`Profiles request failed: ${response.status}`)
  }

  const profiles = (await response.json()) as BuildingProfileMap
  if (Object.keys(profiles).length === 0) {
    throw new Error(
      `No energy profiles found for ${date}. Reseed Tiger with the current 3-month dataset.`,
    )
  }
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

export async function fetchWeather(date: string): Promise<WeatherHour[]> {
  const response = await fetch(`${API_BASE_URL}/api/weather?date=${encodeURIComponent(date)}`)
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
  date: string,
): Promise<EnergyState[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/buildings/${slug}/simulate?date=${encodeURIComponent(date)}`,
    {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(interventions),
    },
  )

  if (!response.ok) {
    throw new Error(`Simulation request failed for ${slug}: ${response.status}`)
  }

  const rows = (await response.json()) as EnergyState[]
  if (rows.length !== 96) {
    throw new Error(`Expected 96 simulated rows for ${slug}, received ${rows.length}`)
  }
  return rows
}


export type AskTempleTwinResponse = {
  answer: string
  model: string
  building_slug: string | null
  date: string
  hour: number
}

export async function askTempleTwin(
  question: string,
  context: { buildingSlug?: string | null; date: string; hour: number },
): Promise<AskTempleTwinResponse> {
  const response = await fetch(`${API_BASE_URL}/api/ask-temple-twin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      building_slug: context.buildingSlug ?? null,
      date: context.date,
      hour: context.hour,
    }),
  })

  if (!response.ok) {
    let detail = `Ask Temple Twin request failed: ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Keep the status-based fallback when the backend did not return JSON.
    }
    throw new Error(detail)
  }

  return (await response.json()) as AskTempleTwinResponse
}

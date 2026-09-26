import type { BuildingProfileMap, BuildingSlug, HourlyState } from '../types/energy'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function fetchProfile(slug: BuildingSlug): Promise<HourlyState[]> {
  const response = await fetch(`${API_BASE_URL}/api/buildings/${slug}/profile`)
  if (!response.ok) {
    throw new Error(`Profile request failed for ${slug}: ${response.status}`)
  }

  const rows = (await response.json()) as HourlyState[]
  if (rows.length !== 24) {
    throw new Error(`Expected 24 hourly rows for ${slug}, received ${rows.length}`)
  }

  return [...rows].sort((a, b) => a.hour - b.hour)
}

export async function fetchAllProfiles(): Promise<BuildingProfileMap> {
  const [serc, beury, engineering] = await Promise.all([
    fetchProfile('serc'),
    fetchProfile('beury'),
    fetchProfile('engineering'),
  ])

  return { serc, beury, engineering }
}

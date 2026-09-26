import type { BuildingProfileMap, BuildingSlug, EnergyState } from '../types/energy'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function fetchProfile(slug: BuildingSlug): Promise<EnergyState[]> {
  const response = await fetch(`${API_BASE_URL}/api/buildings/${slug}/profile`)
  if (!response.ok) {
    throw new Error(`Profile request failed for ${slug}: ${response.status}`)
  }

  const rows = (await response.json()) as EnergyState[]
  if (rows.length !== 96) {
    throw new Error(`Expected 96 15-minute rows for ${slug}, received ${rows.length}`)
  }

  return [...rows].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  )
}

export async function fetchAllProfiles(): Promise<BuildingProfileMap> {
  const [serc, beury, engineering] = await Promise.all([
    fetchProfile('serc'),
    fetchProfile('beury'),
    fetchProfile('engineering'),
  ])
  return { serc, beury, engineering }
}

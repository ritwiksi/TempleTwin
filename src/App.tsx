import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
  ConstantProperty,
  ClassificationType,
  Color,
  ColorMaterialProperty,
  createGooglePhotorealistic3DTileset,
  Entity,
  Ion,
  IonGeocodeProviderType,
  LabelStyle,
  Math as CesiumMath,
  NearFarScalar,
  DistanceDisplayCondition,
  PolygonHierarchy,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Viewer,
  VerticalOrigin,
} from 'cesium'
import { deriveEnergyIntensityThresholds, getEnergyIntensityColor } from './config/energy'
import { BuildingDetailPanel } from './components/BuildingDetailPanel'
import { AskTempleTwin } from './components/AskTempleTwin'
import {
  fetchAllProfiles,
  fetchBuildings,
  fetchSimulationConfig,
  fetchWeather,
  simulateInterventions,
} from './services/api'
import type {
  BuildingMetadata,
  BuildingProfileMap,
  BuildingSlug,
  EnergyState,
  InterventionFlags,
  SimulationConfig,
  WeatherHour,
} from './types/energy'

type Mode = 'reality' | 'energy'

const PLAY_INTERVAL_MS = 180
const DEFAULT_VIEW_DATE = '2018-09-14'

function getStatusColor(
  intensityWPerFt2: number,
  thresholds: { moderate: number; high: number; veryHigh: number },
): string {
  if (intensityWPerFt2 >= thresholds.veryHigh) return '#d56565'
  if (intensityWPerFt2 >= thresholds.high) return '#cf8a58'
  if (intensityWPerFt2 >= thresholds.moderate) return '#d2b25e'
  return '#6fbd87'
}

const EMPTY_INTERVENTIONS: InterventionFlags = {
  led: false,
  hvac: false,
  solar: false,
}

type XY = { x: number; y: number }

function pointInPolygon(point: XY, polygon: XY[]): boolean {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i]
    const b = polygon[j]
    const intersects =
      a.y > point.y !== b.y > point.y &&
      point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y || 1e-9) + a.x
    if (intersects) inside = !inside
  }
  return inside
}

function buildSolarPanelFootprints(building: BuildingMetadata): number[][] {
  const raw: Array<[number, number]> = []
  for (let index = 0; index < building.footprint.length; index += 2) {
    raw.push([building.footprint[index], building.footprint[index + 1]])
  }
  if (raw.length < 3) return []

  const first = raw[0]
  const last = raw[raw.length - 1]
  if (Math.abs(first[0] - last[0]) < 1e-9 && Math.abs(first[1] - last[1]) < 1e-9) {
    raw.pop()
  }

  const centerLon = raw.reduce((sum, point) => sum + point[0], 0) / raw.length
  const centerLat = raw.reduce((sum, point) => sum + point[1], 0) / raw.length
  const metersPerLon = 111_320 * Math.cos(CesiumMath.toRadians(centerLat))
  const metersPerLat = 110_540

  const local = raw.map(([lon, lat]) => ({
    x: (lon - centerLon) * metersPerLon,
    y: (lat - centerLat) * metersPerLat,
  }))

  let edgeAngle = 0
  let longestEdge = 0
  for (let index = 0; index < local.length; index += 1) {
    const a = local[index]
    const b = local[(index + 1) % local.length]
    const dx = b.x - a.x
    const dy = b.y - a.y
    const length = Math.hypot(dx, dy)
    if (length > longestEdge) {
      longestEdge = length
      edgeAngle = Math.atan2(dy, dx)
    }
  }

  const ux = Math.cos(edgeAngle)
  const uy = Math.sin(edgeAngle)
  const vx = -uy
  const vy = ux
  const projections = local.map((point) => ({
    u: point.x * ux + point.y * uy,
    v: point.x * vx + point.y * vy,
  }))
  const minU = Math.min(...projections.map((point) => point.u))
  const maxU = Math.max(...projections.map((point) => point.u))
  const minV = Math.min(...projections.map((point) => point.v))
  const maxV = Math.max(...projections.map((point) => point.v))
  const roofWidth = maxU - minU
  const roofDepth = maxV - minV

  const usableWidth = roofWidth * 0.68
  const usableDepth = roofDepth * 0.56
  const panelWidth = Math.min(Math.max(usableWidth / 5.8, 2.6), 4.8)
  const panelDepth = Math.min(Math.max(usableDepth / 4.8, 1.5), 2.5)
  const columnGap = Math.max(panelWidth * 0.22, 0.6)
  const rowGap = Math.max(panelDepth * 0.35, 0.7)
  const columns = Math.max(
    2,
    Math.min(6, Math.floor((usableWidth + columnGap) / (panelWidth + columnGap))),
  )
  const rows = Math.max(
    2,
    Math.min(5, Math.floor((usableDepth + rowGap) / (panelDepth + rowGap))),
  )
  const arrayWidth = columns * panelWidth + (columns - 1) * columnGap
  const arrayDepth = rows * panelDepth + (rows - 1) * rowGap

  const results: number[][] = []
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const centerU = -arrayWidth / 2 + panelWidth / 2 + column * (panelWidth + columnGap)
      const centerV = -arrayDepth / 2 + panelDepth / 2 + row * (panelDepth + rowGap)
      const cornersUV: Array<[number, number]> = [
        [centerU - panelWidth / 2, centerV - panelDepth / 2],
        [centerU + panelWidth / 2, centerV - panelDepth / 2],
        [centerU + panelWidth / 2, centerV + panelDepth / 2],
        [centerU - panelWidth / 2, centerV + panelDepth / 2],
      ]
      const cornersXY = cornersUV.map(([u, v]) => ({
        x: u * ux + v * vx,
        y: u * uy + v * vy,
      }))
      if (!cornersXY.every((point) => pointInPolygon(point, local))) continue

      const degrees: number[] = []
      for (const point of cornersXY) {
        degrees.push(
          centerLon + point.x / metersPerLon,
          centerLat + point.y / metersPerLat,
        )
      }
      results.push(degrees)
    }
  }

  return results.slice(0, 24)
}

function App() {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const viewerInstanceRef = useRef<Viewer | null>(null)
  const realityTilesRef = useRef<Cesium3DTileset | null>(null)
  const energyEntitiesRef = useRef<Map<BuildingSlug, Entity>>(new Map())
  const solarEntitiesRef = useRef<Map<BuildingSlug, Entity[]>>(new Map())
  const labelEntitiesRef = useRef<Entity[]>([])
  const dayCacheRef = useRef(
    new Map<string, { profiles: BuildingProfileMap; weather: WeatherHour[] }>(),
  )
  const modeRef = useRef<Mode>('reality')

  const [viewerReady, setViewerReady] = useState(false)
  const [mode, setMode] = useState<Mode>('reality')
  const [simulation, setSimulation] = useState<SimulationConfig | null>(null)
  const [profiles, setProfiles] = useState<BuildingProfileMap | null>(null)
  const [scenarioProfiles, setScenarioProfiles] = useState<
    Partial<Record<BuildingSlug, EnergyState[]>>
  >({})
  const [interventions, setInterventions] = useState<
    Record<BuildingSlug, InterventionFlags>
  >({})
  const [simulatingSlug, setSimulatingSlug] = useState<BuildingSlug | null>(null)
  const [buildings, setBuildings] = useState<BuildingMetadata[]>([])
  const [weather, setWeather] = useState<WeatherHour[] | null>(null)
  const [selectedSlug, setSelectedSlug] = useState<BuildingSlug | null>(null)
  const [currentIndex, setCurrentIndex] = useState(48)
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dataError, setDataError] = useState<string | null>(null)
  const [isDataLoading, setIsDataLoading] = useState(true)
  const [showMethodology, setShowMethodology] = useState(false)
  const [buildingSearch, setBuildingSearch] = useState('')

  const currentDate = useMemo(() => {
    if (!simulation) return null
    const dayOffset = Math.floor(currentIndex / simulation.intervals_per_day)
    const date = new Date(`${simulation.start_date}T00:00:00`)
    date.setDate(date.getDate() + dayOffset)
    return [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, '0'),
      String(date.getDate()).padStart(2, '0'),
    ].join('-')
  }, [simulation, currentIndex])

  const currentDayIndex = simulation
    ? currentIndex % simulation.intervals_per_day
    : 0

  const loadTwinData = async () => {
    setIsDataLoading(true)
    setDataError(null)
    try {
      const [simulationData, buildingData] = await Promise.all([
        fetchSimulationConfig(),
        fetchBuildings(),
      ])
      setSimulation(simulationData)
      setBuildings(buildingData)

      const simulationStart = new Date(`${simulationData.start_date}T00:00:00`)
      const preferredStart = new Date(`${DEFAULT_VIEW_DATE}T00:00:00`)
      const dayOffset = Math.max(
        0,
        Math.floor(
          (preferredStart.getTime() - simulationStart.getTime()) /
            (24 * 60 * 60 * 1000),
        ),
      )
      const preferredIndex =
        dayOffset * simulationData.intervals_per_day +
        Math.floor(simulationData.intervals_per_day / 2)
      setCurrentIndex(
        Math.min(preferredIndex, simulationData.total_intervals - 1),
      )
    } catch (err) {
      console.error('Temple Twin metadata fetch failed:', err)
      setDataError('Temple Twin data could not be loaded from the API.')
      setIsDataLoading(false)
    }
  }

  useEffect(() => {
    void loadTwinData()
  }, [])

  useEffect(() => {
    if (!currentDate) return
    let cancelled = false

    const loadDay = async () => {
      const cached = dayCacheRef.current.get(currentDate)
      if (cached) {
        setProfiles(cached.profiles)
        setWeather(cached.weather)
        setDataError(null)
        setIsDataLoading(false)

        const activeScenarios: Partial<Record<BuildingSlug, EnergyState[]>> = {}
        for (const [slug, flags] of Object.entries(interventions)) {
          if (flags.led || flags.hvac || flags.solar) {
            try {
              activeScenarios[slug] = await simulateInterventions(
                slug,
                flags,
                currentDate,
              )
            } catch (err) {
              console.warn(
                `Intervention refresh failed for ${slug} on cached day ${currentDate}`,
                err,
              )
            }
          }
        }
        if (!cancelled) setScenarioProfiles(activeScenarios)
        return
      }

      setIsDataLoading(profiles === null)
      try {
        const [profileData, weatherData] = await Promise.all([
          fetchAllProfiles(currentDate),
          fetchWeather(currentDate),
        ])

        if (cancelled) return

        dayCacheRef.current.set(currentDate, {
          profiles: profileData,
          weather: weatherData,
        })
        setProfiles(profileData)
        setWeather(weatherData)
        setDataError(null)

        const activeScenarios: Partial<Record<BuildingSlug, EnergyState[]>> = {}
        for (const [slug, flags] of Object.entries(interventions)) {
          if (flags.led || flags.hvac || flags.solar) {
            try {
              activeScenarios[slug] = await simulateInterventions(
                slug,
                flags,
                currentDate,
              )
            } catch (err) {
              console.warn(
                `Intervention refresh failed for ${slug} on ${currentDate}`,
                err,
              )
            }
          }
        }
        if (!cancelled) setScenarioProfiles(activeScenarios)
      } catch (err) {
        console.error('Temple Twin daily data fetch failed:', err)
        if (!cancelled) {
          // Keep playback state intact and retain the last good campus frame during transient
          // date-load failures. Only show the full error when we have no data yet.
          if (!profiles) {
            setDataError(`Energy data could not be loaded for ${currentDate}.`)
          }
        }
      } finally {
        if (!cancelled) setIsDataLoading(false)
      }
    }

    void loadDay()
    return () => {
      cancelled = true
    }
  }, [currentDate])

  useEffect(() => {
    if (!isPlaying || !simulation) return
    const timer = window.setInterval(() => {
      setCurrentIndex((index) => (index + 1) % simulation.total_intervals)
    }, PLAY_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [isPlaying, simulation])

  useEffect(() => {
    if (!simulation || !currentDate || currentDayIndex < 64) return

    const date = new Date(`${currentDate}T00:00:00`)
    const end = new Date(`${simulation.end_date}T00:00:00`)
    if (date >= end) return

    date.setDate(date.getDate() + 1)
    const nextDate = [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, '0'),
      String(date.getDate()).padStart(2, '0'),
    ].join('-')

    if (dayCacheRef.current.has(nextDate)) return

    void Promise.all([
      fetchAllProfiles(nextDate),
      fetchWeather(nextDate),
    ])
      .then(([nextProfiles, nextWeather]) => {
        dayCacheRef.current.set(nextDate, {
          profiles: nextProfiles,
          weather: nextWeather,
        })
      })
      .catch((err) => {
        console.warn(`Temple Twin prefetch failed for ${nextDate}`, err)
      })
  }, [simulation, currentDate, currentDayIndex])


  useEffect(() => {
    if (!viewerRef.current) return

    const token = import.meta.env.VITE_CESIUM_ION_TOKEN
    if (!token) {
      setError('Add VITE_CESIUM_ION_TOKEN to .env to load the campus.')
      return
    }

    Ion.defaultAccessToken = token

    const viewer = new Viewer(viewerRef.current, {
      animation: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: IonGeocodeProviderType.GOOGLE,
      globe: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      timeline: false,
      navigationHelpButton: false,
      shouldAnimate: true,
    })

    viewerInstanceRef.current = viewer
    setViewerReady(true)

    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = true
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false

    let disposed = false
    const clickHandler = new ScreenSpaceEventHandler(viewer.scene.canvas)
    clickHandler.setInputAction((movement: { position: Cartesian2 }) => {
      const picks = viewer.scene.drillPick(movement.position, 12)
      const entityId = picks
        .map((picked) => picked?.id?.id)
        .find(
          (id) =>
            typeof id === 'string' &&
            (id.startsWith('energy-') ||
              id.startsWith('label-') ||
              id.startsWith('solar-')),
        )

      if (typeof entityId !== 'string') return

      const slug = entityId.startsWith('energy-')
        ? entityId.replace('energy-', '')
        : entityId.startsWith('label-')
          ? entityId.replace('label-', '')
          : entityId.replace('solar-', '').replace(/-\d+$/, '')

      viewer.camera.cancelFlight()
      setSelectedSlug(slug)
    }, ScreenSpaceEventType.LEFT_CLICK)

    const initialize = async () => {
      try {
        const realityTiles = await createGooglePhotorealistic3DTileset({
          onlyUsingWithGoogleGeocoder: true,
        })
        if (disposed) return
        realityTilesRef.current = realityTiles
        viewer.scene.primitives.add(realityTiles)
        setError(null)
      } catch (err) {
        console.error('Temple Twin Cesium tiles failed:', err)
        const detail = err instanceof Error ? err.message : String(err)
        setError(`Reality mode unavailable: ${detail}`)
      }

      if (!disposed) {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(-75.1498, 39.9814, 820),
          orientation: {
            heading: CesiumMath.toRadians(270),
            pitch: CesiumMath.toRadians(-34),
            roll: 0,
          },
          duration: 1.8,
        })
      }
    }

    void initialize()

    return () => {
      disposed = true
      setViewerReady(false)
      energyEntitiesRef.current.clear()
      solarEntitiesRef.current.clear()
      labelEntitiesRef.current = []
      if (!clickHandler.isDestroyed()) clickHandler.destroy()
      viewerInstanceRef.current = null
      if (!viewer.isDestroyed()) viewer.destroy()
    }
  }, [])

  useEffect(() => {
    const viewer = viewerInstanceRef.current
    if (!viewer || !viewerReady || buildings.length === 0) return

    for (const entity of energyEntitiesRef.current.values()) {
      viewer.entities.remove(entity)
    }
    for (const entity of labelEntitiesRef.current) {
      viewer.entities.remove(entity)
    }
    energyEntitiesRef.current.clear()
    labelEntitiesRef.current = []

    for (const building of buildings) {
      const polygon = viewer.entities.add({
        id: `energy-${building.slug}`,
        name: building.name,
        show: modeRef.current === 'energy',
        polygon: {
          hierarchy: new PolygonHierarchy(
            Cartesian3.fromDegreesArray(building.footprint),
          ),
          material: new ColorMaterialProperty(
            Color.fromCssColorString('#6fbd87').withAlpha(0.62),
          ),
          classificationType: ClassificationType.CESIUM_3D_TILE,
        },
      })
      energyEntitiesRef.current.set(building.slug, polygon)

      const label = viewer.entities.add({
        id: `label-${building.slug}`,
        position: Cartesian3.fromDegrees(
          building.longitude,
          building.latitude,
          building.approx_height_m + 3,
        ),
        label: {
          text: building.name.replace(/\s+/g, ' ').trim(),
          font: "600 15px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          fillColor: Color.fromCssColorString('#244236'),
          outlineColor: Color.fromCssColorString('#F7F8F4'),
          outlineWidth: 1,
          style: LabelStyle.FILL_AND_OUTLINE,
          showBackground: true,
          backgroundColor: Color.fromCssColorString('#F7F8F4').withAlpha(0.98),
          backgroundPadding: new Cartesian2(9, 6),
          verticalOrigin: VerticalOrigin.BOTTOM,
          pixelOffset: new Cartesian2(0, -8),
          scaleByDistance: new NearFarScalar(220, 1.0, 1500, 0.76),
          translucencyByDistance: new NearFarScalar(900, 1, 1550, 0.18),
          distanceDisplayCondition: new DistanceDisplayCondition(0, 1650),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      })
      labelEntitiesRef.current.push(label)
    }

    return () => {
      if (viewer.isDestroyed()) return
      for (const entity of energyEntitiesRef.current.values()) {
        viewer.entities.remove(entity)
      }
      for (const entity of labelEntitiesRef.current) {
        viewer.entities.remove(entity)
      }
      energyEntitiesRef.current.clear()
      labelEntitiesRef.current = []
    }
  }, [buildings, viewerReady])

  useEffect(() => {
    modeRef.current = mode
    const showEnergy = mode === 'energy'
    for (const entity of energyEntitiesRef.current.values()) {
      entity.show = showEnergy
    }
    for (const entities of solarEntitiesRef.current.values()) {
      for (const entity of entities) entity.show = showEnergy
    }
    if (mode === 'reality') {
      setIsPlaying(false)
      setSelectedSlug(null)
    }
  }, [mode])

  useEffect(() => {
    const viewer = viewerInstanceRef.current
    if (!viewer || !viewerReady) return

    const activeSolar = new Set(
      Object.entries(interventions)
        .filter(([, flags]) => flags.solar)
        .map(([slug]) => slug),
    )

    for (const [slug, entities] of solarEntitiesRef.current.entries()) {
      if (activeSolar.has(slug)) {
        for (const entity of entities) entity.show = modeRef.current === 'energy'
        continue
      }
      for (const entity of entities) viewer.entities.remove(entity)
      solarEntitiesRef.current.delete(slug)
    }

    for (const slug of activeSolar) {
      if (solarEntitiesRef.current.has(slug)) continue
      const building = buildings.find((item) => item.slug === slug)
      if (!building) continue

      const panelFootprints = buildSolarPanelFootprints(building)
      const entities = panelFootprints.map((footprint, index) =>
        viewer.entities.add({
          id: `solar-${slug}-${index}`,
          name: `${building.name} rooftop solar`,
          show: modeRef.current === 'energy',
          polygon: {
            hierarchy: new PolygonHierarchy(Cartesian3.fromDegreesArray(footprint)),
            material: new ColorMaterialProperty(
              Color.fromCssColorString('#12304A').withAlpha(0.96),
            ),
            classificationType: ClassificationType.CESIUM_3D_TILE,
          },
        }),
      )
      solarEntitiesRef.current.set(slug, entities)
    }
  }, [interventions, buildings, viewerReady])

  const thresholds = useMemo(() => {
    if (!profiles) return { moderate: 0, high: 0, veryHigh: 0 }
    return deriveEnergyIntensityThresholds(
      Object.values(profiles).flatMap((rows) =>
        rows.map((row) => row.energy_intensity_w_ft2),
      ),
    )
  }, [profiles])

  useEffect(() => {
    if (!profiles) return
    const viewer = viewerInstanceRef.current

    for (const building of buildings) {
      const activeProfile = scenarioProfiles[building.slug] ?? profiles[building.slug]
      const state = activeProfile?.[currentDayIndex]
      const polygon = energyEntitiesRef.current.get(building.slug)?.polygon
      if (!state || !polygon) continue

      const baseColor = Color.fromCssColorString(
        getEnergyIntensityColor(state.energy_intensity_w_ft2, thresholds),
      )
      const isSelected = building.slug === selectedSlug
      const displayColor = isSelected
        ? Color.lerp(baseColor, Color.WHITE, 0.24, new Color())
        : baseColor

      polygon.material = new ColorMaterialProperty(
        displayColor.withAlpha(isSelected ? 0.94 : 0.68),
      )

      const label = viewer?.entities.getById(`label-${building.slug}`)?.label
      if (label) {
        label.scale = new ConstantProperty(isSelected ? 1.08 : 1.0)
        label.backgroundColor = new ConstantProperty(
          isSelected
            ? Color.fromCssColorString('#DCE9E2').withAlpha(0.99)
            : Color.fromCssColorString('#F7F8F4').withAlpha(0.98),
        )
      }
    }
  }, [buildings, profiles, scenarioProfiles, currentDayIndex, thresholds, selectedSlug])

  const currentStates = useMemo(() => {
    if (!profiles) return null
    return buildings.flatMap((building) => {
      const activeProfile = scenarioProfiles[building.slug] ?? profiles[building.slug]
      const state = activeProfile?.[currentDayIndex]
      return state ? [{ ...building, state }] : []
    })
  }, [buildings, profiles, scenarioProfiles, currentDayIndex])

  const rankedCurrentStates = useMemo(
    () =>
      currentStates
        ? [...currentStates].sort((a, b) => b.state.demand_kw - a.state.demand_kw)
        : null,
    [currentStates],
  )

  const filteredCurrentStates = useMemo(() => {
    if (!rankedCurrentStates) return null
    const query = buildingSearch.trim().toLowerCase()
    if (!query) return rankedCurrentStates
    return rankedCurrentStates.filter(({ name }) =>
      name.replace(/\s+/g, ' ').toLowerCase().includes(query),
    )
  }, [rankedCurrentStates, buildingSearch])

  const maxCurrentDemandKw = rankedCurrentStates?.[0]?.state.demand_kw ?? 0

  const selectedBuilding = useMemo(
    () => buildings.find((building) => building.slug === selectedSlug) ?? null,
    [buildings, selectedSlug],
  )

  const reportedElectricityCount = useMemo(
    () => buildings.filter((b) => b.data_confidence === 'reported-electricity').length,
    [buildings],
  )

  const currentClockHour = Math.floor(currentDayIndex / 4)
  const currentMinute = (currentDayIndex % 4) * 15
  const timeLabel = `${String(currentClockHour).padStart(2, '0')}:${String(currentMinute).padStart(2, '0')}`
  const currentWeather = weather?.[currentClockHour] ?? null
  const dateLabel = currentDate
    ? new Date(`${currentDate}T00:00:00`).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : 'Loading date'
  const startDateLabel = simulation
    ? new Date(`${simulation.start_date}T00:00:00`).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
    : ''
  const endDateLabel = simulation
    ? new Date(`${simulation.end_date}T00:00:00`).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
    : ''

  const weatherLabel = (() => {
    if (!currentWeather) return 'Weather unavailable'
    const code = currentWeather.weather_code
    if (code === 0) return 'Clear'
    if (code <= 3) return 'Partly Cloudy'
    if (code <= 48) return 'Fog'
    if (code <= 67) return 'Rain'
    if (code <= 77) return 'Snow'
    if (code <= 82) return 'Showers'
    if (code <= 99) return 'Thunderstorm'
    return 'Weather'
  })()

  const stepInterval = (delta: number) => {
    setIsPlaying(false)
    if (!simulation) return
    setCurrentIndex(
      (index) => (index + delta + simulation.total_intervals) % simulation.total_intervals,
    )
  }

  const resetCamera = () => {
    const viewer = viewerInstanceRef.current
    if (!viewer) return
    viewer.camera.cancelFlight()
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(-75.1498, 39.9814, 820),
      orientation: {
        heading: CesiumMath.toRadians(270),
        pitch: CesiumMath.toRadians(-39),
        roll: 0,
      },
      duration: 1.0,
    })
  }

  const focusBuilding = (building: BuildingMetadata) => {
    const viewer = viewerInstanceRef.current
    setSelectedSlug(building.slug)
    setBuildingSearch('')

    if (!viewer) return

    viewer.camera.cancelFlight()
    const cameraHeight = Math.max(240, building.approx_height_m * 7)
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(
        building.longitude,
        building.latitude,
        cameraHeight,
      ),
      orientation: {
        heading: 0,
        pitch: CesiumMath.toRadians(-90),
        roll: 0,
      },
      duration: 1.0,
    })
  }

  const toggleIntervention = async (
    slug: BuildingSlug,
    key: keyof InterventionFlags,
  ) => {
    if (!currentDate || simulatingSlug === slug) return

    setIsPlaying(false)

    const previousFlags = interventions[slug] ?? EMPTY_INTERVENTIONS
    const nextFlags = { ...previousFlags, [key]: !previousFlags[key] }

    // Update the toggle immediately so the control never feels dead.
    setInterventions((current) => ({ ...current, [slug]: nextFlags }))
    setSimulatingSlug(slug)

    try {
      const simulated = await simulateInterventions(slug, nextFlags, currentDate)
      setScenarioProfiles((current) => ({ ...current, [slug]: simulated }))
    } catch (err) {
      console.error('Temple Twin intervention simulation failed:', err)
      // A scenario that did not successfully compute should not look applied.
      setInterventions((current) => ({ ...current, [slug]: previousFlags }))
      setScenarioProfiles((current) => {
        const next = { ...current }
        delete next[slug]
        return next
      })
      setDataError(
        `Could not apply ${key.toUpperCase()} for this building. The scenario was reset to baseline.`,
      )
    } finally {
      setSimulatingSlug(null)
    }
  }

  const selectedProfile =
    selectedBuilding && profiles
      ? scenarioProfiles[selectedBuilding.slug] ?? profiles[selectedBuilding.slug]
      : null

  return (
    <main className={`app-shell ${mode === 'energy' ? 'energy-mode' : ''}`}>
      <div ref={viewerRef} className="viewer" />

      <div className="brand-shell">
        <div className="brand-copy">
          <div className="eyebrow">TEMPLE TWIN</div>
          <div className="subtitle">
            3D Campus Digital Twin
          </div>
        </div>
      </div>

      <div className="mode-shell">
        <div className="mode-switch" role="group" aria-label="Visualization mode">
          <button
            type="button"
            className={mode === 'reality' ? 'active' : ''}
            onClick={() => setMode('reality')}
          >
            Reality
          </button>
          <button
            type="button"
            className={mode === 'energy' ? 'active' : ''}
            onClick={() => setMode('energy')}
          >
            Energy
          </button>
        </div>
      </div>

      <div className="status-shell">
        <div className="status-copy">
          {mode === 'energy' && currentWeather ? (
            <>
              <strong>{dateLabel} · {timeLabel}</strong>
              <span>{currentWeather.temperature_f.toFixed(0)}°F · {weatherLabel}</span>
            </>
          ) : (
            <>
              <strong>Main Campus</strong>
              <span>Philadelphia · PA</span>
            </>
          )}
        </div>
        <button className="reset-view-button" type="button" onClick={resetCamera}>
          Reset view
        </button>
      </div>

      {mode === 'energy' && (
        <>
          <div className="ask-twin-shell">
            <AskTempleTwin
              buildingSlug={selectedBuilding?.slug ?? null}
              date={currentDate}
              hour={currentClockHour}
              onBeforeAsk={() => setIsPlaying(false)}
              suggestedPrompts={
                selectedBuilding
                  ? [
                      'Why is demand high right now?',
                      'How would solar affect this building?',
                    ]
                  : [
                      'What is driving campus load?',
                      'Why is demand high right now?',
                    ]
              }
            />
          </div>

          <aside
            className={`energy-dock ${selectedBuilding ? 'detail-open' : ''}`}
            aria-label="Building energy panel"
          >
            {selectedBuilding && profiles && selectedProfile ? (
              <BuildingDetailPanel
                building={selectedBuilding}
                baselineProfile={profiles[selectedBuilding.slug]}
                profile={selectedProfile}
                currentIndex={currentDayIndex}
                interventions={interventions[selectedBuilding.slug] ?? EMPTY_INTERVENTIONS}
                isSimulating={simulatingSlug === selectedBuilding.slug}
                onToggle={(key) => void toggleIntervention(selectedBuilding.slug, key)}
                onClose={() => setSelectedSlug(null)}
              />
            ) : (
              <>
                <div className="dock-head">
                  <div>
                    <div className="dock-kicker">energy overview</div>
                    <div className="dock-title">Campus load · {buildings.length} buildings</div>
                  </div>
                </div>

                <div className="building-search">
                  <span className="building-search-icon" aria-hidden="true">⌕</span>
                  <input
                    type="search"
                    value={buildingSearch}
                    onChange={(event) => setBuildingSearch(event.target.value)}
                    placeholder="Search campus buildings"
                    aria-label="Search campus buildings"
                  />
                  {buildingSearch && (
                    <button
                      type="button"
                      className="search-clear"
                      onClick={() => setBuildingSearch('')}
                      aria-label="Clear building search"
                    >
                      ×
                    </button>
                  )}
                </div>

                {dataError ? (
                  <div className="data-error-state">
                    <strong>Energy data unavailable</strong>
                    <span>{dataError}</span>
                    <button type="button" onClick={() => void loadTwinData()}>Retry</button>
                  </div>
                ) : isDataLoading || !filteredCurrentStates ? (
                  <div className="loading-state">
                    <span className="loading-dot" />
                    <span>Loading campus profiles…</span>
                  </div>
                ) : (
                  <>
                    <div className="building-list">
                      {filteredCurrentStates.map(({ slug, name, state }) => {
                        const statusColor = getStatusColor(
                          state.energy_intensity_w_ft2,
                          thresholds,
                        )
                        const loadPercent =
                          maxCurrentDemandKw > 0
                            ? (state.demand_kw / maxCurrentDemandKw) * 100
                            : 0

                        return (
                          <button
                            className="building-row"
                            type="button"
                            key={slug}
                            onClick={() => {
                              const building = buildings.find((item) => item.slug === slug)
                              if (building) focusBuilding(building)
                            }}
                          >
                            <div className="building-row-content">
                              <div className="building-row-main">
                                <span
                                  className="building-status"
                                  style={{ background: statusColor }}
                                />
                                <div>
                                  <div className="metric-name">{name}</div>
                                  <div className="metric-intensity">
                                    {state.energy_intensity_w_ft2.toFixed(2)} W/ft²
                                  </div>
                                </div>
                              </div>
                              <div className="metric-demand">
                                <strong>{state.demand_kw.toFixed(0)}</strong>
                                <span> kW</span>
                              </div>
                            </div>
                            <span className="building-load-track" aria-hidden="true">
                              <span
                                className="building-load-fill"
                                style={{ width: `${loadPercent}%`, background: statusColor }}
                              />
                            </span>
                          </button>
                        )
                      })}
                    </div>

                    {filteredCurrentStates.length === 0 && (
                      <div className="search-empty">
                        No building matches “{buildingSearch}”.
                      </div>
                    )}

                    <div className="overview-legend" aria-label="Energy intensity legend">
                      <div className="overview-divider" />
                      <div className="legend-title">energy intensity</div>
                      <div className="legend-ramp" />
                      <div className="legend-axis">
                        <span>low</span>
                        <span>moderate</span>
                        <span>high</span>
                        <span>very high</span>
                      </div>
                      <div className="legend-values">
                        <span>&lt; {thresholds.moderate.toFixed(2)}</span>
                        <span>{thresholds.high.toFixed(2)}</span>
                        <span>≥ {thresholds.veryHigh.toFixed(2)} W/ft²</span>
                      </div>
                      <div className="legend-formula">
                        demand (W) ÷ floor area (ft²)
                      </div>
                    </div>
                  </>
                )}
              </>
            )}
          </aside>

          <section className="timeline" aria-label="Three-month energy timeline">
            <button className="icon-button" type="button" onClick={() => stepInterval(-1)} aria-label="Previous 15 minutes">‹</button>
            <button
              type="button"
              className="play-button"
              onClick={() => setIsPlaying((playing) => !playing)}
              disabled={!profiles}
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? '❚❚' : '▶'}
            </button>
            <div className="timeline-main">
              <div className="timeline-header timeline-header-centered">
                <strong>{dateLabel} · {timeLabel}</strong>
              </div>
              <input
                type="range"
                min="0"
                max={Math.max((simulation?.total_intervals ?? 1) - 1, 0)}
                step="1"
                value={currentIndex}
                onChange={(event) => {
                  setIsPlaying(false)
                  setCurrentIndex(Number(event.target.value))
                }}
                aria-label="15-minute interval"
              />
            </div>
            <button className="icon-button" type="button" onClick={() => stepInterval(1)} aria-label="Next 15 minutes">›</button>
          </section>
        </>
      )}

      <div className="methodology-shell">
        <button
          className="methodology-button"
          type="button"
          aria-expanded={showMethodology}
          onClick={() => setShowMethodology((visible) => !visible)}
        >
          Modeled estimates
        </button>
        {showMethodology && (
          <div className="methodology-popover">
            <strong>About the energy model</strong>
            <p>
              All {buildings.length || 50} buildings use Temple GIS floor area and
              real campus geometry. {reportedElectricityCount} annual electricity
              totals are matched to Philadelphia 2024 benchmarking; the remainder
              use Temple FY2025 campus EUI calibration. Every 15-minute profile uses
              NREL ComStock, historical Philadelphia weather, and EPA eGRID carbon.
              The interactive timeline spans Sep 1 through Nov 30, 2018.
            </p>
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
    </main>
  )
}

export default App

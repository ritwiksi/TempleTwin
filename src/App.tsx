import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
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
  PolygonHierarchy,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Viewer,
  VerticalOrigin,
} from 'cesium'
import { deriveEnergyIntensityThresholds, getEnergyIntensityColor } from './config/energy'
import { BuildingDetailPanel } from './components/BuildingDetailPanel'
import { fetchAllProfiles, fetchBuildings, fetchWeather, simulateInterventions } from './services/api'
import type {
  BuildingMetadata,
  BuildingProfileMap,
  BuildingSlug,
  EnergyState,
  InterventionFlags,
  WeatherHour,
} from './types/energy'

type Mode = 'reality' | 'energy'

type FocusBuilding = {
  slug: BuildingSlug
  name: string
  longitude: number
  latitude: number
  height: number
  footprint: number[]
}

const BUILDINGS: FocusBuilding[] = [
  {
    slug: 'serc',
    name: 'SERC',
    longitude: -75.15304,
    latitude: 39.98198,
    height: 43,
    footprint: [
      -75.15342, 39.98166,
      -75.15268, 39.98166,
      -75.15268, 39.98228,
      -75.15342, 39.98228,
    ],
  },
  {
    slug: 'beury',
    name: 'Beury Hall',
    longitude: -75.15449,
    latitude: 39.98210,
    height: 34,
    footprint: [
      -75.15486, 39.98184,
      -75.15413, 39.98184,
      -75.15413, 39.98236,
      -75.15486, 39.98236,
    ],
  },
  {
    slug: 'engineering',
    name: 'Engineering Building',
    longitude: -75.15283,
    latitude: 39.98257,
    height: 28,
    footprint: [
      -75.15316, 39.98233,
      -75.15249, 39.98233,
      -75.15249, 39.98282,
      -75.15316, 39.98282,
    ],
  },
]

const PLAY_INTERVAL_MS = 180

function getScadaStatusColor(
  intensityWPerFt2: number,
  thresholds: { moderate: number; high: number; veryHigh: number },
): string {
  if (intensityWPerFt2 >= thresholds.veryHigh) return '#ff3b30'
  if (intensityWPerFt2 >= thresholds.high) return '#ff9500'
  if (intensityWPerFt2 >= thresholds.moderate) return '#ffd60a'
  return '#34c759'
}

const EMPTY_INTERVENTIONS: InterventionFlags = {
  led: false,
  hvac: false,
  solar: false,
}

const DEFAULT_INTERVENTIONS: Record<BuildingSlug, InterventionFlags> = {
  serc: { ...EMPTY_INTERVENTIONS },
  beury: { ...EMPTY_INTERVENTIONS },
  engineering: { ...EMPTY_INTERVENTIONS },
}

function App() {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const viewerInstanceRef = useRef<Viewer | null>(null)
  const realityTilesRef = useRef<Cesium3DTileset | null>(null)
  const energyEntitiesRef = useRef<Map<BuildingSlug, Entity>>(new Map())

  const [mode, setMode] = useState<Mode>('reality')
  const [profiles, setProfiles] = useState<BuildingProfileMap | null>(null)
  const [scenarioProfiles, setScenarioProfiles] = useState<
    Partial<Record<BuildingSlug, EnergyState[]>>
  >({})
  const [interventions, setInterventions] = useState<
    Record<BuildingSlug, InterventionFlags>
  >(DEFAULT_INTERVENTIONS)
  const [isSimulating, setIsSimulating] = useState(false)
  const [buildings, setBuildings] = useState<BuildingMetadata[]>([])
  const [weather, setWeather] = useState<WeatherHour[] | null>(null)
  const [selectedSlug, setSelectedSlug] = useState<BuildingSlug | null>(null)
  const [currentIndex, setCurrentIndex] = useState(48)
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dataError, setDataError] = useState<string | null>(null)
  const [isDataLoading, setIsDataLoading] = useState(true)
  const [showMethodology, setShowMethodology] = useState(false)

  const loadTwinData = async () => {
    setIsDataLoading(true)
    setDataError(null)

    try {
      const [profileData, weatherData, buildingData] = await Promise.all([
        fetchAllProfiles(),
        fetchWeather(),
        fetchBuildings(),
      ])
      setProfiles(profileData)
      setWeather(weatherData)
      setBuildings(buildingData)
    } catch (err) {
      console.error('Temple Twin profile fetch failed:', err)
      setDataError('Energy data could not be loaded from the Temple Twin API.')
    } finally {
      setIsDataLoading(false)
    }
  }

  useEffect(() => {
    void loadTwinData()
  }, [])

  useEffect(() => {
    if (!isPlaying) return

    const timer = window.setInterval(() => {
      setCurrentIndex((index) => (index + 1) % 96)
    }, PLAY_INTERVAL_MS)

    return () => window.clearInterval(timer)
  }, [isPlaying])

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

    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = true
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false

    let disposed = false
    let clickHandler: ScreenSpaceEventHandler | null = null

    const addPermanentLabels = () => {
      for (const building of BUILDINGS) {
        viewer.entities.add({
          position: Cartesian3.fromDegrees(
            building.longitude,
            building.latitude,
            building.height + 3,
          ),
          label: {
            text: building.name,
            font: "600 13px 'Cascadia Code', 'Source Code Pro', Menlo, Monaco, monospace",
            fillColor: Color.fromCssColorString('#244236'),
            outlineColor: Color.TRANSPARENT,
            outlineWidth: 0,
            style: LabelStyle.FILL,
            showBackground: true,
            backgroundColor: Color.fromCssColorString('#F7F8F4').withAlpha(0.94),
            backgroundPadding: new Cartesian2(9, 6),
            verticalOrigin: VerticalOrigin.BOTTOM,
            pixelOffset: new Cartesian2(0, -10),
            scaleByDistance: new NearFarScalar(250, 1.1, 2500, 0.72),
            translucencyByDistance: new NearFarScalar(1800, 1, 5500, 0),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        })
      }
    }

    const addEnergyHighlights = () => {
      for (const building of BUILDINGS) {
        const entity = viewer.entities.add({
          id: `energy-${building.slug}`,
          name: building.name,
          show: false,
          polygon: {
            hierarchy: new PolygonHierarchy(
              Cartesian3.fromDegreesArray(building.footprint),
            ),
            material: new ColorMaterialProperty(
              Color.fromCssColorString('#22c55e').withAlpha(0.62),
            ),
            classificationType: ClassificationType.CESIUM_3D_TILE,
          },
        })

        energyEntitiesRef.current.set(building.slug, entity)
      }
    }

    const initialize = async () => {
      try {
        const realityTiles = await createGooglePhotorealistic3DTileset({
          onlyUsingWithGoogleGeocoder: true,
        })
        if (disposed) return

        realityTilesRef.current = realityTiles
        viewer.scene.primitives.add(realityTiles)

        addEnergyHighlights()
        addPermanentLabels()

        clickHandler = new ScreenSpaceEventHandler(viewer.scene.canvas)
        clickHandler.setInputAction((movement: { position: Cartesian2 }) => {
          const picked = viewer.scene.pick(movement.position)
          const entityId = picked?.id?.id
          if (typeof entityId === 'string' && entityId.startsWith('energy-')) {
            setSelectedSlug(entityId.replace('energy-', '') as BuildingSlug)
          }
        }, ScreenSpaceEventType.LEFT_CLICK)

        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(-75.1597, 39.9764, 820),
          orientation: {
            heading: CesiumMath.toRadians(34),
            pitch: CesiumMath.toRadians(-33),
            roll: 0,
          },
          duration: 3.4,
        })
      } catch (err) {
        console.error('Temple Twin Cesium initialization failed:', err)
        const detail = err instanceof Error ? err.message : String(err)
        setError(`Campus view failed: ${detail}`)
      }
    }

    void initialize()

    return () => {
      disposed = true
      energyEntitiesRef.current.clear()
      if (clickHandler && !clickHandler.isDestroyed()) clickHandler.destroy()
      viewerInstanceRef.current = null
      if (!viewer.isDestroyed()) viewer.destroy()
    }
  }, [])

  useEffect(() => {
    if (realityTilesRef.current) realityTilesRef.current.show = true

    const showEnergy = mode === 'energy'
    for (const entity of energyEntitiesRef.current.values()) {
      entity.show = showEnergy
    }

    if (mode === 'reality') {
      setIsPlaying(false)
      setSelectedSlug(null)
    }
  }, [mode])

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

    for (const building of BUILDINGS) {
      const activeProfile = scenarioProfiles[building.slug] ?? profiles[building.slug]
      const state = activeProfile[currentIndex]
      const entity = energyEntitiesRef.current.get(building.slug)
      const polygon = entity?.polygon

      if (!state || !polygon) continue

      const color = Color.fromCssColorString(
        getEnergyIntensityColor(state.energy_intensity_w_ft2, thresholds),
      ).withAlpha(0.68)

      polygon.material = new ColorMaterialProperty(color)
    }
  }, [profiles, scenarioProfiles, currentIndex, thresholds])

  const currentStates = useMemo(() => {
    if (!profiles) return null
    return BUILDINGS.map((building) => {
      const activeProfile = scenarioProfiles[building.slug] ?? profiles[building.slug]
      return {
        ...building,
        state: activeProfile[currentIndex],
      }
    })
  }, [profiles, scenarioProfiles, currentIndex])

  const rankedCurrentStates = useMemo(() => {
    if (!currentStates) return null
    return [...currentStates].sort((a, b) => b.state.demand_kw - a.state.demand_kw)
  }, [currentStates])

  const maxCurrentDemandKw = useMemo(
    () => rankedCurrentStates?.[0]?.state.demand_kw ?? 0,
    [rankedCurrentStates],
  )

  const selectedBuilding = useMemo(
    () => buildings.find((building) => building.slug === selectedSlug) ?? null,
    [buildings, selectedSlug],
  )


  const currentClockHour = Math.floor(currentIndex / 4)
  const currentMinute = (currentIndex % 4) * 15
  const timeLabel = `${String(currentClockHour).padStart(2, '0')}:${String(currentMinute).padStart(2, '0')}`
  const currentWeather = weather?.[currentClockHour] ?? null

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
    setCurrentIndex((index) => (index + delta + 96) % 96)
  }

  const resetCamera = () => {
    const viewer = viewerInstanceRef.current
    if (!viewer) return

    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(-75.1597, 39.9764, 820),
      orientation: {
        heading: CesiumMath.toRadians(34),
        pitch: CesiumMath.toRadians(-33),
        roll: 0,
      },
      duration: 1.1,
    })
  }

  const toggleIntervention = async (
    slug: BuildingSlug,
    key: keyof InterventionFlags,
  ) => {
    const nextFlags = {
      ...interventions[slug],
      [key]: !interventions[slug][key],
    }

    setIsSimulating(true)
    setDataError(null)

    try {
      const simulated = await simulateInterventions(slug, nextFlags)
      setInterventions((current) => ({ ...current, [slug]: nextFlags }))
      setScenarioProfiles((current) => ({ ...current, [slug]: simulated }))
    } catch (err) {
      console.error('Temple Twin intervention simulation failed:', err)
      setDataError('Could not update the intervention scenario. Check the FastAPI server.')
    } finally {
      setIsSimulating(false)
    }
  }

  return (
    <main className={`app-shell ${mode === 'energy' ? 'energy-mode' : ''}`}>
      <div ref={viewerRef} className="viewer" />

      <div className="brand-shell">
        <div className="brand-mark">T</div>
        <div className="brand-copy">
          <div className="eyebrow">TEMPLE TWIN</div>
          <div className="subtitle">Campus energy digital twin</div>
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
              <strong>{timeLabel}</strong>
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
          <aside className={`energy-dock ${selectedBuilding ? 'detail-open' : ''}`} aria-label="Building energy panel">
            {selectedBuilding && profiles ? (
              <BuildingDetailPanel
                building={selectedBuilding}
                baselineProfile={profiles[selectedBuilding.slug]}
                profile={scenarioProfiles[selectedBuilding.slug] ?? profiles[selectedBuilding.slug]}
                currentIndex={currentIndex}
                interventions={interventions[selectedBuilding.slug]}
                isSimulating={isSimulating}
                onToggle={(key) => void toggleIntervention(selectedBuilding.slug, key)}
                onClose={() => setSelectedSlug(null)}
              />
            ) : (
              <>
                <div className="dock-head">
                  <div>
                    <div className="dock-kicker">energy overview</div>
                    <div className="dock-title">Campus load</div>
                  </div>
                </div>

                {dataError ? (
                  <div className="data-error-state">
                    <strong>Energy data unavailable</strong>
                    <span>{dataError}</span>
                    <button type="button" onClick={() => void loadTwinData()}>Retry</button>
                  </div>
                ) : isDataLoading || !rankedCurrentStates ? (
                  <div className="loading-state">
                    <span className="loading-dot" />
                    <span>Loading modeled building profiles…</span>
                  </div>
                ) : (
                  <>
                    <div className="building-list">
                      {rankedCurrentStates.map(({ slug, name, state }) => {
                        const statusColor = getScadaStatusColor(
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
                            onClick={() => setSelectedSlug(slug)}
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
                            <span
                              className="building-load-track"
                              aria-hidden="true"
                            >
                              <span
                                className="building-load-fill"
                                style={{
                                  width: `${loadPercent}%`,
                                  background: statusColor,
                                }}
                              />
                            </span>
                          </button>
                        )
                      })}
                    </div>

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

          <section className="timeline" aria-label="Friday energy timeline">
            <button className="icon-button" type="button" onClick={() => stepInterval(-1)} aria-label="Previous 15 minutes">
              ‹
            </button>
            <button
              type="button"
              className="play-button"
              onClick={() => setIsPlaying((playing) => !playing)}
              disabled={!profiles}
            >
              {isPlaying ? '❚❚' : '▶'}
            </button>
            <div className="timeline-main">
              <div className="timeline-header">
                <span>00:00</span>
                <strong>{timeLabel}</strong>
                <span>23:45</span>
              </div>
              <input
                type="range"
                min="0"
                max="95"
                step="1"
                value={currentIndex}
                onChange={(event) => {
                  setIsPlaying(false)
                  setCurrentIndex(Number(event.target.value))
                }}
                aria-label="15-minute interval"
              />
            </div>
            <button className="icon-button" type="button" onClick={() => stepInterval(1)} aria-label="Next 15 minutes">
              ›
            </button>
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
          <span className="methodology-icon">i</span>
          Modeled estimates
        </button>
        {showMethodology && (
          <div className="methodology-popover">
            <strong>About the energy model</strong>
            <p>
              Building electricity values are modeled estimates, not Temple meter readings.
              Profiles use Temple public sustainability data, DOE/NREL ComStock, Philadelphia
              weather, and EPA eGRID carbon intensity.
            </p>
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
    </main>
  )
}

export default App

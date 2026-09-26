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
  DistanceDisplayCondition,
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

const PLAY_INTERVAL_MS = 180

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

function App() {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const viewerInstanceRef = useRef<Viewer | null>(null)
  const realityTilesRef = useRef<Cesium3DTileset | null>(null)
  const energyEntitiesRef = useRef<Map<BuildingSlug, Entity>>(new Map())
  const labelEntitiesRef = useRef<Entity[]>([])
  const modeRef = useRef<Mode>('reality')

  const [viewerReady, setViewerReady] = useState(false)
  const [mode, setMode] = useState<Mode>('reality')
  const [profiles, setProfiles] = useState<BuildingProfileMap | null>(null)
  const [scenarioProfiles, setScenarioProfiles] = useState<
    Partial<Record<BuildingSlug, EnergyState[]>>
  >({})
  const [interventions, setInterventions] = useState<
    Record<BuildingSlug, InterventionFlags>
  >({})
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
  const [buildingSearch, setBuildingSearch] = useState('')

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
      console.error('Temple Twin data fetch failed:', err)
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
    setViewerReady(true)

    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = true
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false

    let disposed = false
    const clickHandler = new ScreenSpaceEventHandler(viewer.scene.canvas)
    clickHandler.setInputAction((movement: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(movement.position)
      const entityId = picked?.id?.id
      if (typeof entityId === 'string' && entityId.startsWith('energy-')) {
        setSelectedSlug(entityId.replace('energy-', ''))
      }
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
          destination: Cartesian3.fromDegrees(-75.1562, 39.9805, 1050),
          orientation: {
            heading: CesiumMath.toRadians(28),
            pitch: CesiumMath.toRadians(-39),
            roll: 0,
          },
          duration: 3.0,
        })
      }
    }

    void initialize()

    return () => {
      disposed = true
      setViewerReady(false)
      energyEntitiesRef.current.clear()
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
          scaleByDistance: new NearFarScalar(180, 1.0, 850, 0.82),
          translucencyByDistance: new NearFarScalar(480, 1, 820, 0),
          distanceDisplayCondition: new DistanceDisplayCondition(0, 850),
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
    const viewer = viewerInstanceRef.current

    for (const building of buildings) {
      const activeProfile = scenarioProfiles[building.slug] ?? profiles[building.slug]
      const state = activeProfile?.[currentIndex]
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
        label.scale = isSelected ? 1.08 : 1.0
        label.backgroundColor = isSelected
          ? Color.fromCssColorString('#DCE9E2').withAlpha(0.99)
          : Color.fromCssColorString('#F7F8F4').withAlpha(0.98)
      }
    }
  }, [buildings, profiles, scenarioProfiles, currentIndex, thresholds, selectedSlug])

  const currentStates = useMemo(() => {
    if (!profiles) return null
    return buildings.flatMap((building) => {
      const activeProfile = scenarioProfiles[building.slug] ?? profiles[building.slug]
      const state = activeProfile?.[currentIndex]
      return state ? [{ ...building, state }] : []
    })
  }, [buildings, profiles, scenarioProfiles, currentIndex])

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
      destination: Cartesian3.fromDegrees(-75.1562, 39.9805, 1050),
      orientation: {
        heading: CesiumMath.toRadians(28),
        pitch: CesiumMath.toRadians(-39),
        roll: 0,
      },
      duration: 1.1,
    })
  }

  const focusBuilding = (building: BuildingMetadata) => {
    const viewer = viewerInstanceRef.current
    setSelectedSlug(building.slug)
    setBuildingSearch('')

    if (!viewer) return

    const cameraHeight = Math.max(210, building.approx_height_m * 7)
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(
        building.longitude,
        building.latitude - 0.00018,
        cameraHeight,
      ),
      orientation: {
        heading: 0,
        pitch: CesiumMath.toRadians(-48),
        roll: 0,
      },
      duration: 1.25,
    })
  }

  const toggleIntervention = async (
    slug: BuildingSlug,
    key: keyof InterventionFlags,
  ) => {
    const currentFlags = interventions[slug] ?? EMPTY_INTERVENTIONS
    const nextFlags = { ...currentFlags, [key]: !currentFlags[key] }

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
            {buildings.length ? `${buildings.length}-building campus energy twin` : 'Campus energy digital twin'}
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
              <strong>Friday · {timeLabel}</strong>
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
          <aside
            className={`energy-dock ${selectedBuilding ? 'detail-open' : ''}`}
            aria-label="Building energy panel"
          >
            {selectedBuilding && profiles && selectedProfile ? (
              <BuildingDetailPanel
                building={selectedBuilding}
                baselineProfile={profiles[selectedBuilding.slug]}
                profile={selectedProfile}
                currentIndex={currentIndex}
                interventions={interventions[selectedBuilding.slug] ?? EMPTY_INTERVENTIONS}
                isSimulating={isSimulating}
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

          <section className="timeline" aria-label="Friday energy timeline">
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
              <div className="timeline-header">
                <span>00:00</span>
                <strong>Friday · {timeLabel}</strong>
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
            </p>
          </div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
    </main>
  )
}

export default App

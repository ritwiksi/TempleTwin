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
import { fetchAllProfiles, fetchBuildings, fetchWeather } from './services/api'
import type { BuildingMetadata, BuildingProfileMap, BuildingSlug, WeatherHour } from './types/energy'

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

function App() {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const realityTilesRef = useRef<Cesium3DTileset | null>(null)
  const energyEntitiesRef = useRef<Map<BuildingSlug, Entity>>(new Map())

  const [mode, setMode] = useState<Mode>('reality')
  const [profiles, setProfiles] = useState<BuildingProfileMap | null>(null)
  const [buildings, setBuildings] = useState<BuildingMetadata[]>([])
  const [weather, setWeather] = useState<WeatherHour[] | null>(null)
  const [selectedSlug, setSelectedSlug] = useState<BuildingSlug | null>(null)
  const [currentIndex, setCurrentIndex] = useState(48)
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dataError, setDataError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    Promise.all([fetchAllProfiles(), fetchWeather(), fetchBuildings()])
      .then(([profileData, weatherData, buildingData]) => {
        if (!cancelled) {
          setProfiles(profileData)
          setWeather(weatherData)
          setBuildings(buildingData)
          setDataError(null)
        }
      })
      .catch((err) => {
        console.error('Temple Twin profile fetch failed:', err)
        if (!cancelled) {
          setDataError(
            'Energy data unavailable. Make sure the FastAPI server is running on port 8000.',
          )
        }
      })

    return () => {
      cancelled = true
    }
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
            font: '600 13px Inter, system-ui, sans-serif',
            fillColor: Color.WHITE,
            outlineColor: Color.fromCssColorString('#0B0D11'),
            outlineWidth: 1,
            style: LabelStyle.FILL_AND_OUTLINE,
            showBackground: true,
            backgroundColor: Color.fromCssColorString('#111318').withAlpha(0.88),
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
      const state = profiles[building.slug][currentIndex]
      const entity = energyEntitiesRef.current.get(building.slug)
      const polygon = entity?.polygon

      if (!state || !polygon) continue

      const color = Color.fromCssColorString(
        getEnergyIntensityColor(state.energy_intensity_w_ft2, thresholds),
      ).withAlpha(0.68)

      polygon.material = new ColorMaterialProperty(color)
    }
  }, [profiles, currentIndex, thresholds])

  const currentStates = useMemo(() => {
    if (!profiles) return null
    return BUILDINGS.map((building) => ({
      ...building,
      state: profiles[building.slug][currentIndex],
    }))
  }, [profiles, currentIndex])

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

  return (
    <main className={`app-shell ${mode === 'energy' ? 'energy-mode' : ''}`}>
      <div ref={viewerRef} className="viewer" />

      <header className="topbar">
        <div className="brand">
          <div className="brand-dot" />
          <div>
            <div className="eyebrow">TEMPLE TWIN</div>
            <div className="subtitle">Campus Energy Digital Twin</div>
          </div>
        </div>

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

        <div className="topbar-status">
          {mode === 'energy' && currentWeather ? (
            <>
              <span>{currentWeather.temperature_f.toFixed(0)}°F</span>
              <span className="status-dot">·</span>
              <span>{weatherLabel}</span>
            </>
          ) : (
            <span>Temple University · Philadelphia</span>
          )}
        </div>
      </header>

      {mode === 'energy' && (
        <>
          <aside className={`energy-dock ${selectedBuilding ? 'detail-open' : ''}`} aria-label="Building energy panel">
            {selectedBuilding && profiles ? (
              <BuildingDetailPanel
                building={selectedBuilding}
                profile={profiles[selectedBuilding.slug]}
                currentIndex={currentIndex}
                onClose={() => setSelectedSlug(null)}
              />
            ) : (
              <>
                <div className="dock-head">
                  <div>
                    <div className="dock-kicker">ENERGY MODE</div>
                    <div className="dock-title">Campus load</div>
                  </div>
                  <div className="dock-time">{timeLabel}</div>
                </div>

                {dataError ? (
                  <div className="data-error">{dataError}</div>
                ) : !currentStates ? (
                  <div className="loading-copy">Loading Tiger-backed profiles…</div>
                ) : (
                  <div className="building-list">
                    {currentStates.map(({ slug, name, state }) => (
                      <button className="building-row" type="button" key={slug} onClick={() => setSelectedSlug(slug)}>
                        <div className="building-row-main">
                          <span
                            className="building-status"
                            style={{ background: getEnergyIntensityColor(state.energy_intensity_w_ft2, thresholds) }}
                          />
                          <div>
                            <div className="metric-name">{name}</div>
                            <div className="metric-intensity">
                              {state.energy_intensity_w_ft2.toFixed(2)} W/ft²
                            </div>
                          </div>
                        </div>
                        <div className="metric-demand">
                          {state.demand_kw.toFixed(0)}
                          <span> kW</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </aside>

          <aside className="energy-legend" aria-label="Energy intensity legend">
            <div className="legend-title">Energy intensity</div>
            <div className="legend-ramp" />
            <div className="legend-axis">
              <span>Low</span>
              <span>Moderate</span>
              <span>High</span>
              <span>Very high</span>
            </div>
            <div className="legend-values">
              <span>&lt; {thresholds.moderate.toFixed(2)}</span>
              <span>{thresholds.high.toFixed(2)}</span>
              <span>≥ {thresholds.veryHigh.toFixed(2)} W/ft²</span>
            </div>
            <div className="legend-formula">
              demand (W) ÷ floor area (ft²)
            </div>
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
              {isPlaying ? 'Pause' : 'Play'}
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

      {error && <div className="error-banner">{error}</div>}
    </main>
  )
}

export default App

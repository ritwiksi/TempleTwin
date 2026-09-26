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
  Viewer,
  VerticalOrigin,
} from 'cesium'
import { ENERGY_INTENSITY_THRESHOLDS, getEnergyIntensityColor } from './config/energy'
import { fetchAllProfiles } from './services/api'
import type { BuildingProfileMap, BuildingSlug } from './types/energy'

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

const PLAY_INTERVAL_MS = 800

function App() {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const realityTilesRef = useRef<Cesium3DTileset | null>(null)
  const energyEntitiesRef = useRef<Map<BuildingSlug, Entity>>(new Map())

  const [mode, setMode] = useState<Mode>('reality')
  const [profiles, setProfiles] = useState<BuildingProfileMap | null>(null)
  const [currentHour, setCurrentHour] = useState(12)
  const [isPlaying, setIsPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dataError, setDataError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    fetchAllProfiles()
      .then((data) => {
        if (!cancelled) {
          setProfiles(data)
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
      setCurrentHour((hour) => (hour + 1) % 24)
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
            font: '600 15px Inter, system-ui, sans-serif',
            fillColor: Color.WHITE,
            outlineColor: Color.fromCssColorString('#0B1118'),
            outlineWidth: 4,
            style: LabelStyle.FILL_AND_OUTLINE,
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
      if (!viewer.isDestroyed()) viewer.destroy()
    }
  }, [])

  useEffect(() => {
    if (realityTilesRef.current) realityTilesRef.current.show = true

    const showEnergy = mode === 'energy'
    for (const entity of energyEntitiesRef.current.values()) {
      entity.show = showEnergy
    }

    if (mode === 'reality') setIsPlaying(false)
  }, [mode])

  useEffect(() => {
    if (!profiles) return

    for (const building of BUILDINGS) {
      const state = profiles[building.slug][currentHour]
      const entity = energyEntitiesRef.current.get(building.slug)
      const polygon = entity?.polygon

      if (!state || !polygon) continue

      const color = Color.fromCssColorString(
        getEnergyIntensityColor(state.energy_intensity_w_ft2),
      ).withAlpha(0.68)

      polygon.material = new ColorMaterialProperty(color)
    }
  }, [profiles, currentHour])

  const currentStates = useMemo(() => {
    if (!profiles) return null
    return BUILDINGS.map((building) => ({
      ...building,
      state: profiles[building.slug][currentHour],
    }))
  }, [profiles, currentHour])

  const hourLabel = `${String(currentHour).padStart(2, '0')}:00`

  const stepHour = (delta: number) => {
    setIsPlaying(false)
    setCurrentHour((hour) => (hour + delta + 24) % 24)
  }

  return (
    <main className={`app-shell ${mode === 'energy' ? 'energy-mode' : ''}`}>
      <div ref={viewerRef} className="viewer" />

      <header className="brand">
        <div className="eyebrow">TEMPLE TWIN</div>
        <div className="subtitle">Campus Energy Digital Twin</div>
      </header>

      <div className="mode-switch" role="group" aria-label="Visualization mode">
        <button
          type="button"
          className={mode === 'reality' ? 'active' : ''}
          onClick={() => setMode('reality')}
        >
          REALITY
        </button>
        <button
          type="button"
          className={mode === 'energy' ? 'active' : ''}
          onClick={() => setMode('energy')}
        >
          ENERGY
        </button>
      </div>

      {mode === 'energy' && (
        <>
          <aside className="energy-legend" aria-label="Energy intensity legend">
            <div className="legend-title">ENERGY INTENSITY</div>
            <div className="legend-formula">
              <span>Current Demand (W)</span>
              <span className="formula-line" />
              <span>Floor Area (ft²)</span>
            </div>
            <div className="legend-scale">
              <div><span className="swatch low" />LOW &lt; {ENERGY_INTENSITY_THRESHOLDS.moderate}</div>
              <div><span className="swatch moderate" />MODERATE</div>
              <div><span className="swatch high" />HIGH</div>
              <div><span className="swatch very-high" />VERY HIGH ≥ {ENERGY_INTENSITY_THRESHOLDS.veryHigh}</div>
            </div>
            <div className="legend-note">W/ft² · same thresholds for all buildings</div>
          </aside>

          <aside className="hour-metrics" aria-label="Current building metrics">
            <div className="metrics-time">FRIDAY · {hourLabel}</div>
            {dataError ? (
              <div className="data-error">{dataError}</div>
            ) : !currentStates ? (
              <div className="loading-copy">Loading Tiger-backed profiles…</div>
            ) : (
              currentStates.map(({ slug, name, state }) => (
                <div className="metric-row" key={slug}>
                  <div>
                    <div className="metric-name">{name}</div>
                    <div className="metric-intensity">
                      {state.energy_intensity_w_ft2.toFixed(2)} W/ft²
                    </div>
                  </div>
                  <div className="metric-demand">{state.demand_kw.toFixed(0)} kW</div>
                </div>
              ))
            )}
          </aside>

          <section className="timeline" aria-label="Friday energy timeline">
            <button type="button" onClick={() => stepHour(-1)} aria-label="Previous hour">
              ‹
            </button>
            <button
              type="button"
              className="play-button"
              onClick={() => setIsPlaying((playing) => !playing)}
              disabled={!profiles}
            >
              {isPlaying ? 'PAUSE' : 'PLAY'}
            </button>
            <div className="timeline-main">
              <div className="timeline-header">
                <span>00:00</span>
                <strong>{hourLabel}</strong>
                <span>23:00</span>
              </div>
              <input
                type="range"
                min="0"
                max="23"
                step="1"
                value={currentHour}
                onChange={(event) => {
                  setIsPlaying(false)
                  setCurrentHour(Number(event.target.value))
                }}
                aria-label="Hour"
              />
            </div>
            <button type="button" onClick={() => stepHour(1)} aria-label="Next hour">
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

import { useEffect, useRef, useState } from 'react'
import {
  Cartesian2,
  Cartesian3,
  Cesium3DTileset,
  ClassificationType,
  Color,
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

type Mode = 'reality' | 'energy'

type FocusBuilding = {
  name: string
  longitude: number
  latitude: number
  height: number
  footprint: number[]
  testIntensityWPerFt2: number
  testColor: string
}

const BUILDINGS: FocusBuilding[] = [
  {
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
    testIntensityWPerFt2: 8.1,
    testColor: '#ef4444',
  },
  {
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
    testIntensityWPerFt2: 5.6,
    testColor: '#f59e0b',
  },
  {
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
    testIntensityWPerFt2: 2.4,
    testColor: '#22c55e',
  },
]

function App() {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const realityTilesRef = useRef<Cesium3DTileset | null>(null)
  const energyEntitiesRef = useRef<Entity[]>([])
  const [mode, setMode] = useState<Mode>('reality')
  const [error, setError] = useState<string | null>(null)

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
        const tint = Color.fromCssColorString(building.testColor).withAlpha(0.62)

        const entity = viewer.entities.add({
          name: `${building.name} — temporary Milestone 2 test intensity ${building.testIntensityWPerFt2} W/ft²`,
          show: false,
          polygon: {
            hierarchy: new PolygonHierarchy(
              Cartesian3.fromDegreesArray(building.footprint),
            ),
            material: tint,
            classificationType: ClassificationType.CESIUM_3D_TILE,
          },
        })

        energyEntitiesRef.current.push(entity)
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
      if (!viewer.isDestroyed()) viewer.destroy()
    }
  }, [])

  useEffect(() => {
    // Keep the photorealistic campus visible in both modes so switching feels
    // like an analytical overlay rather than loading a different city model.
    if (realityTilesRef.current) realityTilesRef.current.show = true

    const showEnergy = mode === 'energy'
    for (const entity of energyEntitiesRef.current) {
      entity.show = showEnergy
    }

    setError(null)
  }, [mode])

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
        <aside className="energy-legend" aria-label="Energy intensity legend">
          <div className="legend-title">ENERGY INTENSITY</div>
          <div className="legend-formula">
            <span>Current Demand (W)</span>
            <span className="formula-line" />
            <span>Floor Area (ft²)</span>
          </div>
          <div className="legend-scale">
            <div><span className="swatch low" />LOW</div>
            <div><span className="swatch moderate" />MODERATE</div>
            <div><span className="swatch high" />HIGH</div>
            <div><span className="swatch very-high" />VERY HIGH</div>
          </div>
          <div className="legend-note">Temporary test colors · Milestone 2</div>
        </aside>
      )}

      {error && <div className="error-banner">{error}</div>}
    </main>
  )
}

export default App

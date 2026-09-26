import { useEffect, useRef, useState } from 'react'
import {
  Cartesian2,
  Cartesian3,
  Color,
  createGooglePhotorealistic3DTileset,
  Ion,
  LabelStyle,
  Math as CesiumMath,
  NearFarScalar,
  Viewer,
  VerticalOrigin,
} from 'cesium'

const BUILDINGS = [
  { name: 'SERC', longitude: -75.15304, latitude: 39.98231, height: 43 },
  { name: 'Beury Hall', longitude: -75.15449, latitude: 39.98210, height: 34 },
  { name: 'Engineering Building', longitude: -75.15283, latitude: 39.98257, height: 28 },
]

function App() {
  const viewerRef = useRef<HTMLDivElement | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!viewerRef.current) return

    const token = import.meta.env.VITE_CESIUM_ION_TOKEN
    if (!token) {
      setError('Add VITE_CESIUM_ION_TOKEN to .env to load the photorealistic campus.')
      return
    }

    Ion.defaultAccessToken = token

    const viewer = new Viewer(viewerRef.current, {
      animation: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      timeline: false,
      navigationHelpButton: false,
      shouldAnimate: true,
    })

    viewer.scene.globe.show = false
    viewer.scene.skyAtmosphere.show = true
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false

    let disposed = false

    const initialize = async () => {
      try {
        const tileset = await createGooglePhotorealistic3DTileset()
        if (disposed) return
        viewer.scene.primitives.add(tileset)

        for (const building of BUILDINGS) {
          viewer.entities.add({
            position: Cartesian3.fromDegrees(
              building.longitude,
              building.latitude,
              building.height,
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
        console.error(err)
        setError('Reality Mode could not load. Check the Cesium ion token and Google Photorealistic 3D Tiles access.')
      }
    }

    void initialize()

    return () => {
      disposed = true
      if (!viewer.isDestroyed()) viewer.destroy()
    }
  }, [])

  return (
    <main className="app-shell">
      <div ref={viewerRef} className="viewer" />
      <header className="brand">
        <div className="eyebrow">TEMPLE TWIN</div>
        <div className="subtitle">Campus Energy Digital Twin</div>
      </header>
      <div className="mode-pill" aria-label="Current mode">REALITY</div>
      {error && <div className="error-banner">{error}</div>}
    </main>
  )
}

export default App

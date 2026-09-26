import type { BuildingMetadata, EnergyState } from '../types/energy'

type Props = {
  building: BuildingMetadata
  profile: EnergyState[]
  currentIndex: number
  onClose: () => void
}

function buildPath(values: number[], width: number, height: number): string {
  if (values.length === 0) return ''
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = Math.max(max - min, 1)
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width
      const y = height - ((value - min) / range) * height
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')
}

export function BuildingDetailPanel({ building, profile, currentIndex, onClose }: Props) {
  const current = profile[currentIndex]
  const fullDayEnergyKwh = profile.reduce((sum, row) => sum + row.demand_kw * 0.25, 0)
  const annualKwh = building.modeled_annual_eui_kwh_ft2 * building.floor_area_ft2
  const fullDayCarbonKg = profile.reduce((sum, row) => sum + (row.carbon_kg ?? 0), 0)

  const width = 280
  const height = 92
  const values = profile.map((row) => row.demand_kw)
  const path = buildPath(values, width, height)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = Math.max(max - min, 1)
  const markerX = (currentIndex / (profile.length - 1)) * width
  const markerY = height - ((current.demand_kw - min) / range) * height

  return (
    <div className="detail-panel">
      <div className="detail-head">
        <div>
          <div className="dock-kicker">BUILDING DETAIL</div>
          <div className="detail-title">{building.name}</div>
        </div>
        <button className="detail-close" type="button" onClick={onClose} aria-label="Close building details">
          ×
        </button>
      </div>

      <div className="detail-grid">
        <div className="detail-stat">
          <span>Current demand</span>
          <strong>{current.demand_kw.toFixed(0)} kW</strong>
        </div>
        <div className="detail-stat">
          <span>Full-day energy</span>
          <strong>{fullDayEnergyKwh.toFixed(0)} kWh</strong>
        </div>
        <div className="detail-stat">
          <span>Modeled annual electricity</span>
          <strong>{(annualKwh / 1_000_000).toFixed(2)} GWh/yr</strong>
        </div>
        <div className="detail-stat">
          <span>Full-day carbon</span>
          <strong>{fullDayCarbonKg.toFixed(0)} kg CO₂e</strong>
        </div>
      </div>

      <div className="chart-block">
        <div className="chart-head">
          <span>24-hour load curve</span>
          <span>{String(current.hour).padStart(2, '0')}:{String((currentIndex % 4) * 15).padStart(2, '0')}</span>
        </div>
        <svg className="load-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Friday electricity demand curve">
          <line x1="0" y1={height} x2={width} y2={height} className="chart-axis" />
          <path d={path} className="chart-line" />
          <line x1={markerX} y1="0" x2={markerX} y2={height} className="chart-marker-line" />
          <circle cx={markerX} cy={markerY} r="3.5" className="chart-marker" />
        </svg>
        <div className="chart-axis-labels">
          <span>00:00</span>
          <span>12:00</span>
          <span>23:45</span>
        </div>
      </div>

      <div className="detail-footnote">
        Carbon uses EPA eGRID RFCE total-output CO₂e. Building electricity is modeled.
      </div>
    </div>
  )
}

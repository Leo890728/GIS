const toPopulationNumber = (value) => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }
  if (value == null) return null
  const normalized = String(value).replaceAll(',', '').trim()
  if (!normalized) return null
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : null
}

export const statZonePopulationStyle = (ctx) => {
  const population = toPopulationNumber(ctx?.properties?.P_CNT)
  if (population == null) {
    return {
      style: {
        pointSize: 4,
        heatWeight: 0.3
      },
      derivedFields: {
        P_CNT: 0
      }
    }
  }

  const normalizedWeight = Math.max(0.3, Math.log10(population + 1))
  const pointSize = Math.min(12, 4 + Math.log10(population + 1) * 1.6)
  return {
    style: {
      pointSize: Number(pointSize.toFixed(2)),
      heatWeight: Number(normalizedWeight.toFixed(3))
    },
    derivedFields: {
      P_CNT: population
    }
  }
}

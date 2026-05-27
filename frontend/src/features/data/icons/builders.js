const drawRoundedRect = (ctx, x, y, width, height, radius) => {
  const r = Math.min(radius, width / 2, height / 2)
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + width - r, y)
  ctx.quadraticCurveTo(x + width, y, x + width, y + r)
  ctx.lineTo(x + width, y + height - r)
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height)
  ctx.lineTo(x + r, y + height)
  ctx.quadraticCurveTo(x, y + height, x, y + height - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}

export const buildTruckIcon = (options = {}) => {
  const color = options.color || '#f2c94c'
  const bodyStroke = options.bodyStroke || '#132238'
  const windowColor = options.windowColor || '#9be2b0'
  const wheelColor = options.wheelColor || '#132238'

  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  ctx.clearRect(0, 0, 64, 64)
  ctx.fillStyle = color
  ctx.strokeStyle = bodyStroke
  ctx.lineWidth = 3

  drawRoundedRect(ctx, 10, 20, 30, 18, 4)
  ctx.fill()
  ctx.stroke()

  drawRoundedRect(ctx, 38, 26, 14, 12, 3)
  ctx.fill()
  ctx.stroke()

  ctx.beginPath()
  ctx.arc(20, 44, 5, 0, Math.PI * 2)
  ctx.arc(44, 44, 5, 0, Math.PI * 2)
  ctx.fillStyle = wheelColor
  ctx.fill()

  ctx.beginPath()
  ctx.moveTo(17, 29)
  ctx.lineTo(24, 29)
  ctx.lineTo(20.5, 35)
  ctx.closePath()
  ctx.fillStyle = windowColor
  ctx.fill()

  return ctx.getImageData(0, 0, 64, 64)
}

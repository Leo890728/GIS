export const solveGarbageRoute = async (apiBaseUrl, payload) => {
  const response = await fetch(`${apiBaseUrl}/api/vrp/solve-garbage`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`路線求解失敗 (${response.status})：${text}`)
  }

  return response.json()
}

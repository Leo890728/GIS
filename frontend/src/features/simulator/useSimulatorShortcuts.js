import { onBeforeUnmount, onMounted } from 'vue'

const SKIP_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'])

// Pure: map a keydown to a transport action name, or null when it should be
// ignored (simulator inactive, or focus is on a form control / the timeline
// slider so the shortcut doesn't double-fire with the control's own handling).
export const resolveShortcutAction = (event, isActive) => {
  if (!isActive) return null
  const target = event.target
  if (
    target &&
    (SKIP_TAGS.has(target.tagName) ||
      target.isContentEditable ||
      target.getAttribute?.('role') === 'slider')
  ) {
    return null
  }
  switch (event.key) {
    case ' ':
    case 'Spacebar':
      return 'togglePlay'
    case 'ArrowLeft':
      return 'stepBack'
    case 'ArrowRight':
      return 'stepForward'
    case 'Home':
      return 'seekStart'
    case 'End':
      return 'seekEnd'
    default:
      return null
  }
}

// Global transport shortcuts for history playback. Registers/unregisters the
// keydown listener over the component lifecycle and delegates to the injected
// transport actions.
export const useSimulatorShortcuts = ({ isActive, togglePlay, stepFrame, seekStart, seekEnd }) => {
  const onGlobalKeydown = (event) => {
    const action = resolveShortcutAction(event, isActive())
    if (!action) return
    switch (action) {
      case 'togglePlay':
        togglePlay()
        break
      case 'stepBack':
        stepFrame(-1)
        break
      case 'stepForward':
        stepFrame(1)
        break
      case 'seekStart':
        seekStart()
        break
      case 'seekEnd':
        seekEnd()
        break
    }
    event.preventDefault()
  }

  onMounted(() => window.addEventListener('keydown', onGlobalKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKeydown))

  return { onGlobalKeydown }
}

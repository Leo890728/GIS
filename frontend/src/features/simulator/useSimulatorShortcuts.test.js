import { describe, expect, it } from 'vitest'
import { resolveShortcutAction } from './useSimulatorShortcuts'

const ev = (key, target = null) => ({ key, target })

describe('resolveShortcutAction', () => {
  it('returns null when the simulator is inactive', () => {
    expect(resolveShortcutAction(ev(' '), false)).toBeNull()
  })

  it('maps transport keys to action names', () => {
    expect(resolveShortcutAction(ev(' '), true)).toBe('togglePlay')
    expect(resolveShortcutAction(ev('Spacebar'), true)).toBe('togglePlay')
    expect(resolveShortcutAction(ev('ArrowLeft'), true)).toBe('stepBack')
    expect(resolveShortcutAction(ev('ArrowRight'), true)).toBe('stepForward')
    expect(resolveShortcutAction(ev('Home'), true)).toBe('seekStart')
    expect(resolveShortcutAction(ev('End'), true)).toBe('seekEnd')
  })

  it('ignores unrelated keys', () => {
    expect(resolveShortcutAction(ev('a'), true)).toBeNull()
    expect(resolveShortcutAction(ev('Enter'), true)).toBeNull()
  })

  it('ignores keys while a form control has focus', () => {
    for (const tagName of ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON']) {
      expect(resolveShortcutAction(ev(' ', { tagName }), true)).toBeNull()
    }
  })

  it('ignores keys while the timeline slider has focus', () => {
    const slider = { tagName: 'DIV', getAttribute: (name) => (name === 'role' ? 'slider' : null) }
    expect(resolveShortcutAction(ev('ArrowRight', slider), true)).toBeNull()
  })

  it('ignores keys while a contenteditable element has focus', () => {
    expect(resolveShortcutAction(ev(' ', { tagName: 'DIV', isContentEditable: true }), true)).toBeNull()
  })

  it('allows shortcuts when focus is on a non-control element', () => {
    const div = { tagName: 'DIV', getAttribute: () => null }
    expect(resolveShortcutAction(ev('ArrowLeft', div), true)).toBe('stepBack')
  })
})

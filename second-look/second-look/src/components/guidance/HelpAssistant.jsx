import { useState, useEffect, useRef } from 'react'
import { HelpCircle, Play, Info, RotateCcw, Keyboard, X } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

export default function HelpAssistant() {
  const {
    helpOpen,
    openHelp,
    closeHelp,
    startTour,
    openExplain,
    resetPreferences,
  } = useGuidance()

  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const menuRef = useRef(null)

  // Close on outside click
  useEffect(() => {
    if (!helpOpen) return
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        closeHelp()
      }
    }
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        if (shortcutsOpen) setShortcutsOpen(false)
        else closeHelp()
      }
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [helpOpen, closeHelp, shortcutsOpen])

  const handleAction = (cb) => {
    closeHelp()
    cb()
  }

  return (
    <>
      {/* Mobile-only subtle floating trigger (desktop uses sidebar Help entry) */}
      <div className="fixed bottom-4 right-4 z-30 lg:hidden">
        <button
          onClick={openHelp}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-ln bg-s1 text-obs shadow-lg shadow-black/60 transition hover:bg-s2"
          aria-label="Open Help Menu"
        >
          <HelpCircle size={18} />
        </button>
      </div>

      {/* Compact Help Menu Modal / Popover */}
      {helpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs animate-in fade-in duration-150">
          <div
            ref={menuRef}
            className="relative w-full max-w-xs rounded-xl border border-ln bg-s1 p-4 shadow-2xl shadow-black/80"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-ln/60 pb-2.5">
              <div className="flex items-center gap-2">
                <HelpCircle size={15} className="text-obs" />
                <h3 className="text-xs font-bold text-tx uppercase tracking-wider">
                  Help & Guidance
                </h3>
              </div>
              <button
                onClick={closeHelp}
                className="rounded p-1 text-mu hover:text-tx transition"
                aria-label="Close"
              >
                <X size={15} />
              </button>
            </div>

            <div className="mt-2 space-y-1">
              <button
                onClick={() => handleAction(() => startTour('welcome'))}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
              >
                <Play size={14} className="text-obs flex-none" />
                <span>Start Guided Tour</span>
              </button>

              <button
                onClick={() => handleAction(openExplain)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
              >
                <Info size={14} className="text-acc flex-none" />
                <span>Explain This Page</span>
              </button>

              <button
                onClick={() => handleAction(resetPreferences)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
              >
                <RotateCcw size={14} className="text-mem flex-none" />
                <span>Restart Onboarding</span>
              </button>

              <button
                onClick={() => {
                  closeHelp()
                  setShortcutsOpen(true)
                }}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
              >
                <Keyboard size={14} className="text-mu flex-none" />
                <span>View Keyboard Shortcuts</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Keyboard Shortcuts Dialog */}
      {shortcutsOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={() => setShortcutsOpen(false)}
        >
          <div
            className="relative w-full max-w-sm rounded-xl border border-ln bg-s1 p-5 shadow-2xl shadow-black/80"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-ln/60 pb-3">
              <div className="flex items-center gap-2">
                <Keyboard size={16} className="text-obs" />
                <h3 className="text-sm font-bold text-tx">Keyboard Shortcuts</h3>
              </div>
              <button
                onClick={() => setShortcutsOpen(false)}
                className="rounded p-1 text-mu hover:text-tx transition"
              >
                <X size={15} />
              </button>
            </div>

            <div className="mt-3 space-y-2 text-xs">
              <div className="flex items-center justify-between rounded-lg border border-ln/60 bg-s2/40 px-3 py-2">
                <span className="text-tx">Skip / Close Modal or Tour</span>
                <kbd className="rounded border border-ln bg-s1 px-2 py-0.5 font-mono text-[11px] text-mu">Esc</kbd>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-ln/60 bg-s2/40 px-3 py-2">
                <span className="text-tx">Next Tour Step</span>
                <kbd className="rounded border border-ln bg-s1 px-2 py-0.5 font-mono text-[11px] text-mu">→</kbd>
              </div>
              <div className="flex items-center justify-between rounded-lg border border-ln/60 bg-s2/40 px-3 py-2">
                <span className="text-tx">Previous Tour Step</span>
                <kbd className="rounded border border-ln bg-s1 px-2 py-0.5 font-mono text-[11px] text-mu">←</kbd>
              </div>
            </div>

            <div className="mt-4 flex justify-end border-t border-ln/60 pt-3">
              <button
                onClick={() => setShortcutsOpen(false)}
                className="rounded-md bg-obs px-3.5 py-1 text-xs font-bold text-[#06201c] hover:bg-obs/90"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

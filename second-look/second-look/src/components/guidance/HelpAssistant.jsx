import { useState, useRef, useEffect } from 'react'
import { HelpCircle, Play, RotateCcw, Cpu, Info, FlaskConical, Wifi, Sparkles, X } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

export default function HelpAssistant() {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  const {
    currentView,
    setView,
    startTour,
    openArchModal,
    openConnModal,
    openExplain,
    resetPreferences,
  } = useGuidance()

  useEffect(() => {
    if (!menuOpen) return
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    const handleKey = (e) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [menuOpen])

  const handleAction = (cb) => {
    setMenuOpen(false)
    cb()
  }

  return (
    <div ref={menuRef} className="fixed bottom-5 right-5 z-40">
      {menuOpen && (
        <div className="mb-2 w-64 rounded-2xl border border-ln bg-s1/95 p-3 shadow-2xl shadow-black/80 backdrop-blur-md animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between border-b border-ln/60 pb-2 px-1">
            <div className="flex items-center gap-1.5 text-xs font-bold text-tx">
              <Sparkles size={14} className="text-obs" />
              <span>Judge Assistant</span>
            </div>
            <button
              onClick={() => setMenuOpen(false)}
              className="rounded p-1 text-mu hover:bg-s2 hover:text-tx"
            >
              <X size={14} />
            </button>
          </div>

          <div className="mt-2 space-y-1">
            <button
              onClick={() => handleAction(() => startTour('welcome'))}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
            >
              <Play size={14} className="text-obs" />
              <span>Start Full Product Tour</span>
            </button>

            {currentView !== 'overview' && (
              <button
                onClick={() => handleAction(() => startTour(currentView))}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
              >
                <RotateCcw size={14} className="text-mem" />
                <span>Tour This Section</span>
              </button>
            )}

            <button
              onClick={() => handleAction(openExplain)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
            >
              <Info size={14} className="text-acc" />
              <span>Explain Current Page</span>
            </button>

            <button
              onClick={() =>
                handleAction(() => {
                  setView('playground')
                })
              }
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
            >
              <FlaskConical size={14} className="text-mem" />
              <span>Try Recovery Scenarios</span>
            </button>

            <button
              onClick={() => handleAction(openArchModal)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
            >
              <Cpu size={14} className="text-obs" />
              <span>Nebius + NVIDIA Architecture</span>
            </button>

            <button
              onClick={() => handleAction(openConnModal)}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium text-tx transition hover:bg-s2 hover:text-obs"
            >
              <Wifi size={14} className="text-ok" />
              <span>Infrastructure & AI Status</span>
            </button>

            <div className="border-t border-ln/60 pt-1 mt-1">
              <button
                onClick={() => handleAction(resetPreferences)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[11px] text-mu transition hover:bg-s2 hover:text-tx"
              >
                <RotateCcw size={12} />
                <span>Reset Onboarding / Welcome</span>
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setMenuOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-ln bg-s1 px-4 py-2.5 text-xs font-bold text-tx shadow-lg shadow-black/60 transition hover:border-obs hover:bg-s2 hover:text-obs"
        data-tour="help-assistant"
      >
        <HelpCircle size={16} className="text-obs" />
        <span>Help & Tour</span>
      </button>
    </div>
  )
}

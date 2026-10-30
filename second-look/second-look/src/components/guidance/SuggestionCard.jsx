import { Sparkles, X, ArrowRight } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'
import { useRobot } from '../../RobotContext.jsx'

export default function SuggestionCard() {
  const {
    activeSuggestion,
    dismissSuggestion,
    startTour,
    openConnModal,
    setView,
  } = useGuidance()
  const { a } = useRobot()

  if (!activeSuggestion) return null

  const handleAction = () => {
    dismissSuggestion(activeSuggestion.id)
    if (activeSuggestion.actionType === 'tour') {
      startTour('welcome')
    } else if (activeSuggestion.actionType === 'start_task') {
      a.start()
    } else if (activeSuggestion.actionType === 'load_example') {
      a.scenario(activeSuggestion.scenario || 'moved')
    } else if (activeSuggestion.actionType === 'navigate') {
      setView(activeSuggestion.view)
    } else if (activeSuggestion.actionType === 'connection_modal') {
      openConnModal()
    }
  }

  return (
    <div
      className="fixed bottom-4 left-4 lg:left-[272px] z-30 max-w-sm rounded-xl border border-obs/40 bg-s1/95 p-3.5 shadow-xl shadow-black/70 backdrop-blur-md animate-in slide-in-from-bottom-3 duration-150"
      style={{ maxWidth: 'calc(100vw - 32px)' }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-obs">
          <Sparkles size={15} />
          <h4 className="text-xs font-bold text-tx">{activeSuggestion.title}</h4>
        </div>
        <button
          onClick={() => dismissSuggestion(activeSuggestion.id)}
          className="rounded p-1 text-mu transition hover:bg-s2 hover:text-tx"
          aria-label="Dismiss suggestion"
        >
          <X size={13} />
        </button>
      </div>

      <p className="mt-1 text-[11.5px] text-mu leading-relaxed">{activeSuggestion.text}</p>

      <div className="mt-2.5 flex items-center justify-end gap-2">
        <button
          onClick={() => dismissSuggestion(activeSuggestion.id)}
          className="px-2 py-1 text-[11px] text-mu hover:text-tx"
        >
          Dismiss
        </button>
        <button
          onClick={handleAction}
          className="flex items-center gap-1 rounded-md bg-obs px-2.5 py-1 text-xs font-bold text-[#06201c] transition hover:bg-obs/90 shadow-sm"
        >
          <span>{activeSuggestion.actionText}</span>
          <ArrowRight size={12} />
        </button>
      </div>
    </div>
  )
}

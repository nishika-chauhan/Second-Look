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
    <div className="fixed bottom-5 right-5 z-40 max-w-sm rounded-xl border border-obs/40 bg-s1/95 p-4 shadow-xl shadow-black/70 backdrop-blur-md animate-in slide-in-from-bottom-5 duration-200">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-obs">
          <Sparkles size={16} />
          <h4 className="text-xs font-bold text-tx">{activeSuggestion.title}</h4>
        </div>
        <button
          onClick={() => dismissSuggestion(activeSuggestion.id)}
          className="rounded p-1 text-mu transition hover:bg-s2 hover:text-tx"
          aria-label="Dismiss suggestion"
        >
          <X size={14} />
        </button>
      </div>

      <p className="mt-1.5 text-xs text-mu leading-relaxed">{activeSuggestion.text}</p>

      <div className="mt-3 flex items-center justify-end gap-2">
        <button
          onClick={() => dismissSuggestion(activeSuggestion.id)}
          className="px-2 py-1 text-[11px] text-mu hover:text-tx"
        >
          Dismiss
        </button>
        <button
          onClick={handleAction}
          className="flex items-center gap-1.5 rounded-lg bg-obs px-3 py-1.5 text-xs font-bold text-[#06201c] transition hover:bg-obs/90 shadow-md shadow-obs/20"
        >
          <span>{activeSuggestion.actionText}</span>
          <ArrowRight size={13} />
        </button>
      </div>
    </div>
  )
}

import { useState, useEffect, useRef, useCallback } from 'react'
import { ArrowLeft, ArrowRight, X, Sparkles, CheckCircle2 } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

export default function SpotlightTour() {
  const {
    tourActive,
    tourStep,
    totalSteps,
    currentStepData,
    nextTourStep,
    prevTourStep,
    skipTour,
  } = useGuidance()

  const [rect, setRect] = useState(null)
  const cardRef = useRef(null)

  // Measure target element position
  const updateRect = useCallback(() => {
    if (!tourActive || !currentStepData) {
      setRect(null)
      return
    }

    const el = document.querySelector(currentStepData.target)
    if (el) {
      const b = el.getBoundingClientRect()
      // Scroll into view if out of viewport
      if (b.top < 0 || b.bottom > window.innerHeight) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
      setRect({
        top: b.top,
        left: b.left,
        width: b.width,
        height: b.height,
        bottom: b.bottom,
        right: b.right,
      })
    } else {
      setRect(null)
    }
  }, [tourActive, currentStepData])

  useEffect(() => {
    updateRect()
    const timer = setTimeout(updateRect, 100)
    const timer2 = setTimeout(updateRect, 350)
    window.addEventListener('resize', updateRect)
    window.addEventListener('scroll', updateRect, true)
    return () => {
      clearTimeout(timer)
      clearTimeout(timer2)
      window.removeEventListener('resize', updateRect)
      window.removeEventListener('scroll', updateRect, true)
    }
  }, [updateRect, tourStep])

  // Keyboard navigation
  useEffect(() => {
    if (!tourActive) return
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        skipTour()
      } else if (e.key === 'ArrowRight') {
        nextTourStep()
      } else if (e.key === 'ArrowLeft') {
        prevTourStep()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [tourActive, nextTourStep, prevTourStep, skipTour])

  if (!tourActive || !currentStepData) return null

  // Calculate Popover Position
  let popoverStyle = {}
  const pad = 12

  if (rect) {
    const isMobile = window.innerWidth < 640
    if (isMobile) {
      // Bottom sheet style on mobile
      popoverStyle = {
        position: 'fixed',
        bottom: '16px',
        left: '16px',
        right: '16px',
        zIndex: 60,
      }
    } else {
      const placement = currentStepData.placement || 'bottom'
      if (placement === 'bottom') {
        const top = rect.bottom + pad
        const left = Math.max(16, Math.min(rect.left, window.innerWidth - 380))
        popoverStyle = { position: 'fixed', top: `${top}px`, left: `${left}px`, zIndex: 60 }
      } else if (placement === 'top') {
        const bottom = window.innerHeight - rect.top + pad
        const left = Math.max(16, Math.min(rect.left, window.innerWidth - 380))
        popoverStyle = { position: 'fixed', bottom: `${bottom}px`, left: `${left}px`, zIndex: 60 }
      } else if (placement === 'right') {
        const left = rect.right + pad
        const top = Math.max(16, Math.min(rect.top, window.innerHeight - 340))
        popoverStyle = { position: 'fixed', top: `${top}px`, left: `${left}px`, zIndex: 60 }
      } else {
        // center or left
        const top = Math.max(60, rect.top)
        const left = Math.max(16, rect.left - 380 - pad)
        popoverStyle = { position: 'fixed', top: `${top}px`, left: `${left}px`, zIndex: 60 }
      }
    }
  } else {
    // Target element not found on current screen -> center modal
    popoverStyle = {
      position: 'fixed',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      zIndex: 60,
    }
  }

  const isLast = tourStep === totalSteps - 1

  return (
    <>
      {/* Dimmed backdrop with spotlight cutout if rect exists */}
      <div
        className="fixed inset-0 z-50 pointer-events-auto transition-all duration-300"
        style={{
          background: 'rgba(0, 0, 0, 0.65)',
        }}
        onClick={nextTourStep}
      />

      {/* Spotlight cutout border */}
      {rect && (
        <div
          className="fixed z-50 pointer-events-none rounded-xl border-2 border-obs transition-all duration-300 shadow-[0_0_0_9999px_rgba(0,0,0,0.65),0_0_24px_rgba(70,196,178,0.4)]"
          style={{
            top: `${rect.top - 4}px`,
            left: `${rect.left - 4}px`,
            width: `${rect.width + 8}px`,
            height: `${rect.height + 8}px`,
          }}
        />
      )}

      {/* Popover Card */}
      <div
        ref={cardRef}
        style={popoverStyle}
        className="w-[calc(100vw-32px)] sm:w-[380px] max-w-[420px] rounded-xl border border-ln bg-s1 p-5 shadow-2xl shadow-black/80 animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-ln/60 pb-3">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 rounded-full bg-obs/15 px-2.5 py-0.5 text-[11px] font-bold text-obs">
              <Sparkles size={12} />
              Step {tourStep + 1} of {totalSteps}
            </span>
          </div>
          <button
            onClick={skipTour}
            className="rounded-lg p-1 text-mu transition hover:bg-s2 hover:text-tx"
            title="Skip tour (Esc)"
          >
            <X size={16} />
          </button>
        </div>

        <div className="mt-3">
          <h3 className="text-base font-bold text-tx">{currentStepData.title}</h3>
          <p className="mt-1.5 text-xs leading-relaxed text-tx/85">{currentStepData.desc}</p>

          {currentStepData.why && (
            <div className="mt-3 rounded-lg border border-ln/80 bg-s2/50 p-2.5">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-mem">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-mem" />
                Why This Matters
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-mu">{currentStepData.why}</p>
            </div>
          )}

          {currentStepData.action && (
            <div className="mt-2.5 flex items-start gap-1.5 text-[11px] text-obs/90">
              <span className="font-semibold text-obs">Suggested action:</span>
              <span>{currentStepData.action}</span>
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-ln/60 pt-3">
          <button
            onClick={skipTour}
            className="text-xs text-mu transition hover:text-tx"
          >
            Skip Tour
          </button>

          <div className="flex items-center gap-2">
            {tourStep > 0 && (
              <button
                onClick={prevTourStep}
                className="flex items-center gap-1 rounded-lg border border-ln bg-s2 px-3 py-1.5 text-xs font-medium text-tx transition hover:bg-s2/80"
              >
                <ArrowLeft size={13} />
                Prev
              </button>
            )}
            <button
              onClick={nextTourStep}
              className="flex items-center gap-1.5 rounded-lg bg-obs px-3.5 py-1.5 text-xs font-bold text-[#06201c] transition hover:bg-obs/90 shadow-md shadow-obs/20"
            >
              {isLast ? (
                <>
                  <CheckCircle2 size={14} />
                  Finish
                </>
              ) : (
                <>
                  Next
                  <ArrowRight size={13} />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

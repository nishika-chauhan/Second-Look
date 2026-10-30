import { useState, useRef, useEffect } from 'react'
import { HelpCircle } from 'lucide-react'
import { TOOLTIPS } from '../../config/guidance/tooltips.js'

export default function InfoTooltip({ tip, title, body, metric, align = 'center', className = '' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const data = tip && TOOLTIPS[tip] ? TOOLTIPS[tip] : { title, body, metric }

  useEffect(() => {
    if (!open) return
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false)
      }
    }
    const handleKey = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  if (!data?.body && !data?.title) return null

  return (
    <span ref={ref} className={`relative inline-flex items-center ${className}`}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="inline-flex items-center text-mu transition hover:text-obs focus:outline-none"
        aria-label={data.title ? `Info: ${data.title}` : 'Help information'}
      >
        <HelpCircle size={13} className="opacity-70 hover:opacity-100" />
      </button>

      {open && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-xl border border-ln bg-s1 p-3 text-left shadow-xl shadow-black/70 animate-in fade-in zoom-in-95 duration-150"
          style={{
            maxWidth: 'calc(100vw - 32px)',
          }}
        >
          {data.title && (
            <span className="block text-xs font-bold text-tx border-b border-ln/60 pb-1 mb-1.5">
              {data.title}
            </span>
          )}
          <span className="block text-[11px] leading-relaxed text-tx/85">
            {data.body}
          </span>
          {data.calculation && (
            <span className="mt-1.5 block rounded bg-s2/60 p-1.5 text-[10px] text-mu border border-ln/40">
              <span className="font-semibold text-mem">Calculation:</span> {data.calculation}
            </span>
          )}
          {data.metric && (
            <span className="mt-1 block text-[10px] font-medium text-obs">
              {data.metric}
            </span>
          )}
        </span>
      )}
    </span>
  )
}

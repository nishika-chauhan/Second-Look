import { useState } from 'react'
import { X, Cpu, Server, Database, Layout, ShieldCheck, ArrowDown, Sparkles } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'
import { TECH_DETAILS } from '../../config/guidance/techDetails.js'

export default function ArchitectureModal() {
  const { archModalOpen, closeArchModal } = useGuidance()
  const [selectedLayer, setSelectedLayer] = useState('nebius_nemotron')

  if (!archModalOpen) return null

  const layers = TECH_DETAILS.architecture.layers

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl rounded-2xl border border-ln bg-s1 p-6 shadow-2xl shadow-black/80 max-h-[90vh] overflow-y-auto sm:p-8">
        <button
          onClick={closeArchModal}
          className="absolute right-4 top-4 rounded-lg p-2 text-mu transition hover:bg-s2 hover:text-tx"
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-obs/15 text-obs">
            <Sparkles size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-obs/30 bg-obs/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-obs">
                Technical Architecture
              </span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-tx">
              Powered by Nebius + NVIDIA
            </h2>
          </div>
        </div>

        <p className="mt-2 text-xs text-mu leading-relaxed sm:text-sm">
          Second Look bridges physical robotics and cloud AI. Spatial sensor discrepancies trigger reasoning cycles via Nebius Token Factory and NVIDIA Nemotron to generate recovery actions.
        </p>

        {/* Hackathon Highlights Banner */}
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-ln/80 bg-s2/60 p-4">
            <div className="flex items-center gap-2">
              <Cpu size={18} className="text-obs" />
              <h3 className="text-xs font-bold text-tx">{TECH_DETAILS.nebius.name}</h3>
            </div>
            <p className="mt-1 text-[11px] font-medium text-obs/90">{TECH_DETAILS.nebius.role}</p>
            <p className="mt-1 text-[11px] leading-relaxed text-mu">{TECH_DETAILS.nebius.summary}</p>
            <ul className="mt-2 space-y-1 text-[10.5px] text-tx/80">
              {TECH_DETAILS.nebius.features.map((f, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-1 h-1 w-1 rounded-full bg-obs flex-none" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-ln/80 bg-s2/60 p-4">
            <div className="flex items-center gap-2">
              <Cpu size={18} className="text-mem" />
              <h3 className="text-xs font-bold text-tx">{TECH_DETAILS.nemotron.name}</h3>
            </div>
            <p className="mt-1 text-[11px] font-medium text-mem/90">{TECH_DETAILS.nemotron.role}</p>
            <p className="mt-1 text-[11px] leading-relaxed text-mu">{TECH_DETAILS.nemotron.summary}</p>
            <ul className="mt-2 space-y-1 text-[10.5px] text-tx/80">
              {TECH_DETAILS.nemotron.features.map((f, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="mt-1 h-1 w-1 rounded-full bg-mem flex-none" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Interactive Data Flow Stack */}
        <div className="mt-6">
          <h3 className="text-xs font-bold uppercase tracking-wider text-mu mb-3">
            System Data Flow & Component Stack
          </h3>

          <div className="space-y-2">
            {layers.map((layer, idx) => {
              const isSelected = selectedLayer === layer.id
              const icons = [Layout, Server, Database, ShieldCheck, Cpu]
              const LayerIcon = icons[idx] || Server

              return (
                <div key={layer.id}>
                  <div
                    onClick={() => setSelectedLayer(layer.id)}
                    className={`cursor-pointer rounded-xl border p-3.5 transition ${
                      isSelected
                        ? 'border-obs bg-s2 shadow-md shadow-obs/10'
                        : 'border-ln/70 bg-s2/40 hover:border-ln hover:bg-s2/70'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-7 w-7 items-center justify-center rounded-lg ${
                            isSelected ? 'bg-obs text-[#06201c]' : 'bg-s1 text-mu'
                          }`}
                        >
                          <LayerIcon size={15} />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-tx">{layer.title}</h4>
                          <span className="text-[10.5px] font-mono text-mu">{layer.tech}</span>
                        </div>
                      </div>
                      <span className="text-[11px] font-medium text-obs">
                        {isSelected ? 'Selected' : 'Details'}
                      </span>
                    </div>

                    {isSelected && (
                      <p className="mt-2.5 border-t border-ln/50 pt-2 text-[11.5px] leading-relaxed text-tx/90">
                        {layer.role}
                      </p>
                    )}
                  </div>

                  {idx < layers.length - 1 && (
                    <div className="flex justify-center py-0.5">
                      <ArrowDown size={14} className="text-mu/50" />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        <div className="mt-6 flex justify-end border-t border-ln/60 pt-4">
          <button
            onClick={closeArchModal}
            className="rounded-lg bg-obs px-5 py-2 text-xs font-bold text-[#06201c] transition hover:bg-obs/90 shadow-md shadow-obs/20"
          >
            Close Architecture
          </button>
        </div>
      </div>
    </div>
  )
}

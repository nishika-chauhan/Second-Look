import { useState, useEffect } from 'react'
import { X, ArrowDown, ArrowRight, Layout, Server, Database, Brain, Cpu, Sparkles, CheckCircle2 } from 'lucide-react'
import { useGuidance } from '../../context/GuidanceContext.jsx'

const ARCH_NODES = [
  {
    id: 'frontend',
    name: 'React Frontend (Vite)',
    category: 'Interface & Visualization',
    icon: Layout,
    color: 'var(--obs)',
    role: 'Provides operator interface for commanding retrieval, triggering disturbance scenarios, and visualizing Bayesian belief distributions.',
    inputs: 'Operator commands, real-time WebSocket telemetry, simulation state',
    outputs: 'Task dispatch (JSON), scenario selection, pause/reset signals',
    contribution: 'Delivers immediate visibility into spatial uncertainty and recovery metrics.',
  },
  {
    id: 'backend',
    name: 'Python FastAPI Backend',
    category: 'Coordination & Telemetry',
    icon: Server,
    color: 'var(--tx)',
    role: 'Coordinates application logic, manages MuJoCo simulation routing, evaluates sensor updates, and proxies inference requests.',
    inputs: 'WebSocket command packets, MuJoCo sensor outputs',
    outputs: 'Broadcasted telemetry events, structured AI prompts, actuator commands',
    contribution: 'Acts as the central operational bridge between physical simulation and AI reasoning.',
  },
  {
    id: 'memory',
    name: 'Warehouse Memory & Belief Tracker',
    category: 'Spatial State Machine',
    icon: Database,
    color: 'var(--mem)',
    role: 'Tracks Bayesian probability distribution across stations (Table A, B, C, Out of View). Updates posteriors dynamically when visual scans succeed or miss.',
    inputs: 'Station camera observation flags (item present vs empty)',
    outputs: 'Updated posterior probabilities (A, B, C, U) and reasoning evidence chain',
    contribution: 'Prevents blind assumption that items are where they were originally stored.',
  },
  {
    id: 'recovery_logic',
    name: 'Autonomous Recovery Planner',
    category: 'Decision Engine & Fallback',
    icon: Brain,
    color: 'var(--acc)',
    role: 'Selects the recovery action path (Trust Memory, Search Elsewhere, Retry Grasp, Request Help). Functions as immediate deterministic fallback if cloud AI is unavailable.',
    inputs: 'Current belief distribution, gripper slip signals, camera scan results',
    outputs: 'Selected recovery path and fallback execution commands',
    contribution: 'Guarantees the warehouse never halts or faults when cloud connectivity drops.',
  },
  {
    id: 'nebius',
    name: 'Nebius Token Factory',
    category: 'Cloud Inference Gateway',
    icon: Cpu,
    color: 'var(--obs)',
    role: 'High-throughput OpenAI-compatible API gateway serving NVIDIA Nemotron models with high availability.',
    inputs: 'Structured JSON prompts containing spatial context, SKU type, and scan history',
    outputs: 'Streamed LLM token responses and model metadata',
    contribution: 'Provides scalable cloud infrastructure to power complex generative reasoning.',
  },
  {
    id: 'nemotron',
    name: 'NVIDIA Nemotron Reasoning Model',
    category: 'Cognitive Reasoning Engine',
    icon: Sparkles,
    color: 'var(--mem)',
    role: 'Configured model (nvidia/nemotron-4-340b-instruct). Evaluates anomalous warehouse situations and generates structured recovery directives with operator justifications.',
    inputs: 'System instructions + JSON spatial context + anomaly description',
    outputs: 'Structured JSON decision: { action, confidence, reasoning }',
    contribution: 'Provides cognitive reasoning over ambiguous edge cases beyond static rules.',
  },
]

export default function ArchitectureModal() {
  const { archModalOpen, closeArchModal } = useGuidance()
  const [selectedNodeId, setSelectedNodeId] = useState('nemotron')

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') closeArchModal()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [closeArchModal])

  if (!archModalOpen) return null

  const selectedNode = ARCH_NODES.find((n) => n.id === selectedNodeId) || ARCH_NODES[0]
  const NodeIcon = selectedNode.icon

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={closeArchModal}
    >
      <div
        className="relative w-full max-w-4xl rounded-2xl border border-ln bg-s1 p-5 shadow-2xl shadow-black/80 max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ln/60 pb-3 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-obs/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-obs border border-obs/30">
                Architecture Explorer
              </span>
              <h2 className="text-lg font-bold tracking-tight text-tx">How Second Look Works</h2>
            </div>
            <p className="text-xs text-mu mt-0.5">
              From warehouse observations to intelligent recovery decisions. Click any component to inspect data flow.
            </p>
          </div>
          <button
            onClick={closeArchModal}
            className="rounded-lg p-1.5 text-mu hover:bg-s2 hover:text-tx transition"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Main 2-Column Explorer: Visual Flow (Left) + Detail Inspector (Right) */}
        <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          {/* Left: Interactive Diagram Flow */}
          <div className="space-y-2">
            <span className="text-[10.5px] font-bold uppercase tracking-wider text-mu block mb-1">
              End-to-End System Pipeline
            </span>

            {/* Step 1: React Frontend */}
            <NodeCard
              node={ARCH_NODES[0]}
              isSelected={selectedNodeId === ARCH_NODES[0].id}
              onClick={() => setSelectedNodeId(ARCH_NODES[0].id)}
            />

            <FlowArrow />

            {/* Step 2: FastAPI Backend */}
            <NodeCard
              node={ARCH_NODES[1]}
              isSelected={selectedNodeId === ARCH_NODES[1].id}
              onClick={() => setSelectedNodeId(ARCH_NODES[1].id)}
            />

            <FlowArrow />

            {/* Step 3: Dual Intelligence: Memory & Recovery Planner */}
            <div className="grid grid-cols-2 gap-2">
              <NodeCard
                node={ARCH_NODES[2]}
                isSelected={selectedNodeId === ARCH_NODES[2].id}
                onClick={() => setSelectedNodeId(ARCH_NODES[2].id)}
              />
              <NodeCard
                node={ARCH_NODES[3]}
                isSelected={selectedNodeId === ARCH_NODES[3].id}
                onClick={() => setSelectedNodeId(ARCH_NODES[3].id)}
              />
            </div>

            <FlowArrow />

            {/* Step 4: AI Layer: Nebius Token Factory */}
            <NodeCard
              node={ARCH_NODES[4]}
              isSelected={selectedNodeId === ARCH_NODES[4].id}
              onClick={() => setSelectedNodeId(ARCH_NODES[4].id)}
            />

            <FlowArrow />

            {/* Step 5: NVIDIA Nemotron */}
            <NodeCard
              node={ARCH_NODES[5]}
              isSelected={selectedNodeId === ARCH_NODES[5].id}
              onClick={() => setSelectedNodeId(ARCH_NODES[5].id)}
            />
          </div>

          {/* Right: Selected Node Detail Panel */}
          <div className="rounded-xl border border-ln bg-s2/50 p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2.5 border-b border-ln/60 pb-3 mb-3">
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-xl"
                  style={{ background: `${selectedNode.color}20`, color: selectedNode.color }}
                >
                  <NodeIcon size={18} />
                </div>
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-mu">
                    {selectedNode.category}
                  </span>
                  <h3 className="text-sm font-bold text-tx leading-tight">{selectedNode.name}</h3>
                </div>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="font-semibold text-tx block mb-0.5">Responsibility:</span>
                  <p className="text-mu text-[11.5px] leading-relaxed">{selectedNode.role}</p>
                </div>

                <div className="rounded-lg border border-ln/50 bg-s1/60 p-2.5 space-y-2">
                  <div>
                    <span className="text-[10.5px] font-bold text-mu uppercase block">Receives (Input):</span>
                    <span className="text-[11px] text-tx/90 font-mono">{selectedNode.inputs}</span>
                  </div>
                  <div>
                    <span className="text-[10.5px] font-bold text-mu uppercase block">Produces (Output):</span>
                    <span className="text-[11px] text-tx/90 font-mono">{selectedNode.outputs}</span>
                  </div>
                </div>

                <div>
                  <span className="font-semibold text-tx block mb-0.5">Contribution to System:</span>
                  <p className="text-mu text-[11.5px] leading-relaxed">{selectedNode.contribution}</p>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-ln/60 flex items-center justify-between text-[11px]">
              <span className="text-mu">Click any node to inspect</span>
              <span className="font-semibold text-obs flex items-center gap-1">
                <CheckCircle2 size={12} />
                Selected
              </span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 flex items-center justify-between border-t border-ln/60 pt-3">
          <span className="text-[11px] text-mu">
            Nebius Token Factory & NVIDIA Nemotron Hackathon Integration
          </span>
          <button
            onClick={closeArchModal}
            className="rounded-lg bg-obs px-4 py-1.5 text-xs font-bold text-[#06201c] hover:bg-obs/90 transition"
          >
            Close Explorer
          </button>
        </div>
      </div>
    </div>
  )
}

function NodeCard({ node, isSelected, onClick }) {
  const Icon = node.icon
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between rounded-xl border p-2.5 text-left transition ${
        isSelected
          ? 'border-obs bg-s2 shadow-md shadow-obs/10 ring-1 ring-obs'
          : 'border-ln/70 bg-s2/30 hover:border-ln hover:bg-s2/60'
      }`}
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          className={`flex h-7 w-7 flex-none items-center justify-center rounded-lg ${
            isSelected ? 'bg-obs text-[#06201c]' : 'bg-s1 text-mu'
          }`}
        >
          <Icon size={14} />
        </div>
        <div className="min-w-0 truncate">
          <h4 className="text-xs font-bold text-tx truncate leading-tight">{node.name}</h4>
          <span className="text-[10px] text-mu truncate block">{node.category}</span>
        </div>
      </div>
      <ArrowRight size={13} className={isSelected ? 'text-obs' : 'text-mu/40'} />
    </button>
  )
}

function FlowArrow() {
  return (
    <div className="flex justify-center py-0.5">
      <ArrowDown size={13} className="text-mu/40" />
    </div>
  )
}

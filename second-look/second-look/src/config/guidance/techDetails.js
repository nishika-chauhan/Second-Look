/**
 * Second Look - Technical Architecture & Hackathon Technology Grounding
 */

export const TECH_DETAILS = {
  projectTitle: 'Second Look — Warehouse Intelligence',
  tagline: 'Autonomous Uncertainty Reasoning & Failure Recovery for Warehouse Robotics',
  hackathon: 'Nebius × NVIDIA AI Hackathon',

  nebius: {
    name: 'Nebius Token Factory',
    role: 'Ultra-Low Latency AI Inference Infrastructure',
    summary: 'High-throughput OpenAI-compatible API gateway delivering NVIDIA Nemotron models at scale.',
    features: [
      'Token throughput optimized for real-time robotic agent decision loops (< 250ms latency target).',
      'Unified API routing between cloud-hosted NVIDIA models and local edge planners.',
      'Stateless request handling with robust fallback to deterministic recovery rules if connectivity drops.',
    ],
    integrationDetails: 'Accessed via https://api.tokenfactory.nebius.com/v1/ with streaming token validation.',
  },

  nemotron: {
    name: 'NVIDIA Nemotron-4 340B / Nemotron Instruct',
    role: 'Reasoning Under Warehouse Uncertainty',
    summary: 'State-of-the-art instruction-following and structured reasoning LLM for automated operational decision-making.',
    features: [
      'Ingests multi-modal warehouse context: spatial belief priors, camera observation timestamps, and gripper slip flags.',
      'Outputs structured recovery actions: Trust Memory, Search Alternative Stations, Re-attempt Physical Grasp, or Escalate to Human Operator.',
      'Generates natural language operator audit logs explaining WHY a recovery path was selected.',
    ],
    promptStructure: 'System Prompt sets warehouse safety policies + Bayesian belief state -> Output JSON { action, confidence, reasoning }',
  },

  architecture: {
    layers: [
      {
        id: 'frontend',
        title: 'React + Vite Frontend',
        tech: 'React 18, TailwindCSS, Recharts, SVG Gantry View',
        role: 'Interactive operator command center, spatial visualization, live belief distribution, and comparative analytics.',
      },
      {
        id: 'backend',
        title: 'Python FastAPI Backend',
        tech: 'FastAPI, Uvicorn, WebSockets, Asyncio',
        role: 'Orchestrates real-time telemetry, handles bi-directional WebSocket streams, and bridges simulation to AI inference.',
      },
      {
        id: 'simulation',
        title: 'MuJoCo Physics Simulation',
        tech: 'MuJoCo 3.x, Cartesian Gantry Model',
        role: 'Models physical workspace, camera field of view, end-effector kinematics, and realistic sensor noise / slip dynamics.',
      },
      {
        id: 'memory_planner',
        title: 'Belief Tracker & Recovery Planner',
        tech: 'Bayesian Update Logic & Rule-Based Fallback',
        role: 'Maintains posterior distributions over locations (Table A, B, C, Out of View) and ensures safe operations even offline.',
      },
      {
        id: 'nebius_nemotron',
        title: 'Nebius Token Factory + NVIDIA Nemotron',
        tech: 'NVIDIA Nemotron-4, Nebius High-Throughput Gateway',
        role: 'Evaluates anomalous states, reasons about missing inventory, and produces structured recovery directives.',
      },
    ],
  },
}

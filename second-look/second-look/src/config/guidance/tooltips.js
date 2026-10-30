/**
 * Second Look - Centralized Tooltips & Explanations
 */

export const TOOLTIPS = {
  // Status Strip
  task: {
    title: 'Current Task',
    body: 'The active warehouse retrieval objective. The robot is commanded to locate, approach, grasp, and retrieve the specified item.',
    metric: 'Goal state: Pick & place target SKU',
  },
  robotState: {
    title: 'Robot Operational State',
    body: 'Current kinematics and task execution phase: Idle, Moving, Scanning, Retrieving, Completed, or Failed. Paused states halt execution cleanly.',
    metric: 'State machine driven by planner events',
  },
  memoryConfidence: {
    title: 'Memory Confidence',
    body: 'Bayesian probability of the target object existing at the highest-likelihood location. Updated in real time as cameras scan or miss objects.',
    metric: 'Range: 0% to 100% posterior probability',
  },
  recoveryStatus: {
    title: 'Recovery Status',
    body: 'Active recovery policy if a disturbance or discrepancy was detected: Standby (nominal), Searching (relocated item), Retrying (grasp slip), or Help (missing item).',
    metric: 'Policy: Autonomous or operator escalated',
  },

  // Memory & Beliefs
  beliefA: {
    title: 'Table A Probability',
    body: 'Prior memory location. If the object was placed here initially, confidence starts high (~92%). If a scan finds Table A empty, probability drops to ~2%.',
    metric: 'Bayesian update with sensor accuracy priors',
  },
  beliefB: {
    title: 'Table B Probability',
    body: 'Adjacent storage workstation. If Table A is empty, probability redistributes proportionally here.',
    metric: 'Alternate search candidate',
  },
  beliefC: {
    title: 'Shelf C Probability',
    body: 'Deep warehouse shelf storage. Secondary candidate location for displaced items.',
    metric: 'Alternate search candidate',
  },
  beliefU: {
    title: 'Out of View (Uncertainty)',
    body: 'Probability mass assigned to the possibility that the item has been removed from all known workstation tables or obscured by occlusions.',
    metric: 'Triggers human assistance when > 80%',
  },

  // Decisions
  decisionTrust: {
    title: 'Trust Memory Path',
    body: 'High confidence (> 80%) that the item remains at its recorded location. The robot proceeds directly to approach and grasp.',
    metric: 'Default nominal policy',
  },
  decisionSearch: {
    title: 'Search Elsewhere Path',
    body: 'Target was missing from its remembered location. The robot evaluates alternative stations in order of decreasing probability.',
    metric: 'Autonomous spatial re-localization',
  },
  decisionRetry: {
    title: 'Retry Grasp Path',
    body: 'The object is verified in view, but the physical grasp slipped. The robot re-aligns the end-effector and attempts a second grasp.',
    metric: 'Mechanical slip recovery',
  },
  decisionHelp: {
    title: 'Request Help Path',
    body: 'All known stations were inspected and the item was not found anywhere in the workspace. An alert is sent to a warehouse operator.',
    metric: 'Escalation to prevent endless looping',
  },

  // Analytics Metrics
  successRate: {
    title: 'Retrieval Success Rate',
    body: 'Percentage of retrieval trials that concluded with the object successfully grasped and transported to the delivery station.',
    calculation: 'Total successful retrievals ÷ Total trials executed (per mode)',
    importance: 'Second Look prevents failure on moved items where memory-only baselines fail 100% of the time.',
    type: 'Session benchmark data',
  },
  recoveryAttempts: {
    title: 'Average Recovery Attempts',
    body: 'Mean count of corrective recovery actions (searches, rescans, grasp retries) required to achieve a successful retrieval.',
    calculation: 'Sum of recovery steps across trials ÷ Total trials executed',
    importance: 'Measures autonomous resilience. Zero indicates nominal tasks; higher numbers reflect recovery under disturbance.',
    type: 'Session benchmark data',
  },
  searchTime: {
    title: 'Average Search & Task Time',
    body: 'Mean duration in seconds from task initiation to final placement or failure state.',
    calculation: 'Total execution seconds ÷ Total trials executed',
    importance: 'Quantifies latency overhead of autonomous recovery versus static execution.',
    type: 'Session benchmark data',
  },

  // System & Connection
  connBackend: {
    title: 'FastAPI Backend',
    body: 'Python FastAPI server handling state coordination, MuJoCo simulation routing, and AI inference requests.',
  },
  connNebius: {
    title: 'Nebius Token Factory',
    body: 'High-throughput cloud inference infrastructure serving NVIDIA models with ultra-low latency for real-time robotic planning.',
  },
  connNemotron: {
    title: 'NVIDIA Nemotron Reasoning Model',
    body: 'NVIDIA Nemotron-4 instruction-tuned model reasoning over spatial evidence, sensor confidence, and recovery risk.',
  },
  connSimulator: {
    title: 'MuJoCo Simulation Engine',
    body: 'Physics-accurate simulation representing cartesian gantry dynamics, end-effector slip friction, and visual field of view.',
  },
}

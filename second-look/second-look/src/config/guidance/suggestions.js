/**
 * Context-aware dynamic suggestions based on current application state
 */

export function getDynamicSuggestion({ view, status, running, trials, conn, decision, scn }) {
  if (view === 'overview') {
    return {
      id: 'tour-suggest',
      title: 'New to Second Look?',
      text: 'Start with the interactive Guided Product Tour to explore how the system reasons under uncertainty.',
      actionText: 'Start Tour',
      actionType: 'tour',
    }
  }

  if (view === 'workstation' && !running && trials.length === 0) {
    return {
      id: 'ws-start-suggest',
      title: 'Ready for First Pick?',
      text: 'Click "Start Task" to watch the cartesian gantry execute a nominal retrieval to Table A.',
      actionText: 'Start Task',
      actionType: 'start_task',
    }
  }

  if (view === 'playground' && !running) {
    return {
      id: 'pg-suggest',
      title: 'Test Disturbance Recovery',
      text: 'Pick "Uncertain Location (Object Moved)" to see how beliefs shift when an item is displaced.',
      actionText: 'Try Moved Example',
      actionType: 'load_example',
      scenario: 'moved',
    }
  }

  if (status === 'completed' && trials.length > 0 && view !== 'analytics') {
    return {
      id: 'analytics-suggest',
      title: 'Evaluate Benchmark Results',
      text: 'Trial completed! Head to Results & Analytics to view comparative charts against the fixed baseline.',
      actionText: 'View Analytics',
      actionType: 'navigate',
      view: 'analytics',
    }
  }

  if (conn === 'simulated' || conn === 'offline') {
    return {
      id: 'demo-mode-suggest',
      title: 'Client-Side Simulation Active',
      text: 'Running in stand-in simulation mode. All retrieval scenarios and belief updates execute locally in real-time.',
      actionText: 'Connection Details',
      actionType: 'connection_modal',
    }
  }

  return null
}

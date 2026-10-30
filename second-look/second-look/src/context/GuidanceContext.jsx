import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react'
import { WELCOME_TOUR, SECTION_TOURS } from '../config/guidance/tours.js'
import { getDynamicSuggestion } from '../config/guidance/suggestions.js'

const GuidanceContext = createContext(null)

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export function GuidanceProvider({ children, currentView, setView, robotState, robotActions }) {
  // Modal states
  const [welcomeOpen, setWelcomeOpen] = useState(() => {
    try {
      return !localStorage.getItem('second_look_welcomed')
    } catch {
      return true
    }
  })
  const [archModalOpen, setArchModalOpen] = useState(false)
  const [connModalOpen, setConnModalOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [explainModalOpen, setExplainModalOpen] = useState(false)

  // Tour states
  const [tourActive, setTourActive] = useState(false)
  const [tourName, setTourName] = useState('welcome')
  const [tourStep, setTourStep] = useState(0)

  // Dismissed suggestions
  const [dismissedSuggestions, setDismissedSuggestions] = useState(new Set())

  // Real-time backend & AI connection status
  const [connStatus, setConnStatus] = useState({
    backend: { status: 'checking', service: 'FastAPI', version: '2.1.0' },
    simulator: { status: 'standby', detail: 'Local simulation active' },
    nebius: { status: 'checking', detail: 'Verifying Token Factory...' },
    nemotron: { status: 'checking', model: 'nvidia/nemotron-4-340b-instruct' },
    mode: 'demo',
    lastCheck: null,
    isChecking: false,
    error: null,
  })

  // Poll / check connection
  const checkConnection = useCallback(async (deepCheck = false) => {
    setConnStatus((prev) => ({ ...prev, isChecking: true }))
    try {
      const url = `${API_BASE}/api/status${deepCheck ? '?check=true' : ''}`
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 2500)
      const res = await fetch(url, { signal: controller.signal })
      clearTimeout(timeoutId)

      if (res.ok) {
        const data = await res.json()
        setConnStatus({
          backend: data.backend || { status: 'connected', service: 'FastAPI' },
          simulator: data.simulator || { status: 'standby', detail: 'Configured' },
          nebius: data.nebius || { status: 'unconfigured', detail: 'NEBIUS_API_KEY unset' },
          nemotron: data.nemotron || { status: 'offline', model: 'nvidia/nemotron-4-340b-instruct' },
          mode: data.mode || 'demo',
          lastCheck: new Date().toLocaleTimeString(),
          isChecking: false,
          error: null,
        })
      } else {
        throw new Error(`HTTP ${res.status}`)
      }
    } catch {
      // Backend offline or unreachable - clean fallback to simulated stand-in
      setConnStatus({
        backend: { status: 'offline', service: 'FastAPI', detail: 'Backend service unreachable at ' + API_BASE },
        simulator: { status: 'standby', detail: 'Client-side simulation running locally' },
        nebius: { status: 'unconfigured', detail: 'Inference gateway offline. Local planner active.' },
        nemotron: { status: 'offline', model: 'nvidia/nemotron-4-340b-instruct', detail: 'Offline. Fast rule-based planner active.' },
        mode: 'demo',
        lastCheck: new Date().toLocaleTimeString(),
        isChecking: false,
        error: 'Unable to reach backend API. Local demonstration mode enabled.',
      })
    }
  }, [])

  // Initial connection check on mount + periodic polling
  useEffect(() => {
    checkConnection(false)
    const interval = setInterval(() => checkConnection(false), 20000)
    return () => clearInterval(interval)
  }, [checkConnection])

  // Current tour steps list
  const activeSteps = useMemo(() => {
    if (tourName === 'welcome') return WELCOME_TOUR
    return SECTION_TOURS[tourName] || WELCOME_TOUR
  }, [tourName])

  const currentStepData = activeSteps[tourStep] || null

  // Ensure user is on the right screen for current tour step
  useEffect(() => {
    if (tourActive && currentStepData && currentStepData.view && currentStepData.view !== currentView) {
      setView(currentStepData.view)
    }
  }, [tourActive, currentStepData, currentView, setView])

  // Tour actions
  const startTour = useCallback((name = 'welcome') => {
    setTourName(name)
    setTourStep(0)
    setTourActive(true)
    setWelcomeOpen(false)
    setHelpOpen(false)
  }, [])

  const nextTourStep = useCallback(() => {
    setTourStep((prev) => {
      if (prev + 1 < activeSteps.length) {
        return prev + 1
      }
      setTourActive(false)
      try {
        localStorage.setItem('second_look_welcomed', 'true')
      } catch {}
      return 0
    })
  }, [activeSteps])

  const prevTourStep = useCallback(() => {
    setTourStep((prev) => Math.max(0, prev - 1))
  }, [])

  const skipTour = useCallback(() => {
    setTourActive(false)
    try {
      localStorage.setItem('second_look_welcomed', 'true')
    } catch {}
  }, [])

  const restartTour = useCallback((name = 'welcome') => {
    startTour(name)
  }, [startTour])

  const handleDismissWelcome = useCallback((start = false) => {
    setWelcomeOpen(false)
    try {
      localStorage.setItem('second_look_welcomed', 'true')
    } catch {}
    if (start) {
      startTour('welcome')
    }
  }, [startTour])

  const resetPreferences = useCallback(() => {
    try {
      localStorage.removeItem('second_look_welcomed')
    } catch {}
    setDismissedSuggestions(new Set())
    setWelcomeOpen(true)
  }, [])

  // Dynamic Suggestion evaluation
  const activeSuggestion = useMemo(() => {
    if (tourActive || welcomeOpen) return null
    const candidate = getDynamicSuggestion({
      view: currentView,
      status: robotState?.status || 'idle',
      running: robotState?.running || false,
      trials: robotState?.trials || [],
      conn: robotState?.conn || 'simulated',
      decision: robotState?.decision || null,
      scn: robotState?.scn || 'normal',
    })
    if (candidate && !dismissedSuggestions.has(candidate.id)) {
      return candidate
    }
    return null
  }, [tourActive, welcomeOpen, currentView, robotState, dismissedSuggestions])

  const dismissSuggestion = useCallback((id) => {
    setDismissedSuggestions((prev) => new Set([...prev, id]))
  }, [])

  const value = {
    // Modals
    welcomeOpen,
    openWelcome: () => setWelcomeOpen(true),
    closeWelcome: () => handleDismissWelcome(false),
    handleDismissWelcome,
    archModalOpen,
    openArchModal: () => setArchModalOpen(true),
    closeArchModal: () => setArchModalOpen(false),
    connModalOpen,
    openConnModal: () => setConnModalOpen(true),
    closeConnModal: () => setConnModalOpen(false),
    helpOpen,
    openHelp: () => setHelpOpen(true),
    closeHelp: () => setHelpOpen(false),
    explainModalOpen,
    openExplain: () => setExplainModalOpen(true),
    closeExplain: () => setExplainModalOpen(false),

    // Tour
    tourActive,
    tourName,
    tourStep,
    totalSteps: activeSteps.length,
    currentStepData,
    startTour,
    nextTourStep,
    prevTourStep,
    skipTour,
    restartTour,

    // Suggestions
    activeSuggestion,
    dismissSuggestion,

    // Connection
    connStatus,
    refreshConnection: checkConnection,

    // General
    resetPreferences,
    currentView,
    setView,
  }

  return <GuidanceContext.Provider value={value}>{children}</GuidanceContext.Provider>
}

export const useGuidance = () => {
  const ctx = useContext(GuidanceContext)
  if (!ctx) throw new Error('useGuidance must be used within GuidanceProvider')
  return ctx
}

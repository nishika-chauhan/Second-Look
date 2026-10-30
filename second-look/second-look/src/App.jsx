import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import StatusStrip from './components/StatusStrip.jsx'
import Overview from './screens/Overview.jsx'
import Workstation from './screens/Workstation.jsx'
import Memory from './screens/Memory.jsx'
import Playground from './screens/Playground.jsx'
import Analytics from './screens/Analytics.jsx'

import { useRobot } from './RobotContext.jsx'
import { GuidanceProvider } from './context/GuidanceContext.jsx'
import WelcomeModal from './components/guidance/WelcomeModal.jsx'
import SpotlightTour from './components/guidance/SpotlightTour.jsx'
import ArchitectureModal from './components/guidance/ArchitectureModal.jsx'
import ConnectionDetailsModal from './components/guidance/ConnectionDetailsModal.jsx'
import ExplainPageModal from './components/guidance/ExplainPageModal.jsx'
import SuggestionCard from './components/guidance/SuggestionCard.jsx'
import HelpAssistant from './components/guidance/HelpAssistant.jsx'
import DemoModeBanner from './components/guidance/DemoModeBanner.jsx'

const SCREENS = {
  overview: Overview,
  workstation: Workstation,
  memory: Memory,
  playground: Playground,
  analytics: Analytics,
}

export default function App() {
  const [view, setView] = useState('overview')
  const { s, a } = useRobot()
  const Screen = SCREENS[view]

  return (
    <GuidanceProvider
      currentView={view}
      setView={setView}
      robotState={s}
      robotActions={a}
    >
      <div className="grid min-h-screen lg:grid-cols-[256px_1fr] bg-bg text-tx antialiased selection:bg-obs/30 selection:text-tx">
        <Sidebar view={view} setView={setView} />
        <main className="flex min-w-0 flex-col gap-3 p-3.5 lg:p-5">
          <DemoModeBanner />
          <StatusStrip />
          <Screen setView={setView} />
        </main>
      </div>

      {/* Global Guidance Modals, Tours, and Assistants */}
      <WelcomeModal />
      <SpotlightTour />
      <ArchitectureModal />
      <ConnectionDetailsModal />
      <ExplainPageModal />
      <SuggestionCard />
      <HelpAssistant />
    </GuidanceProvider>
  )
}

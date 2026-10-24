import { useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import StatusStrip from './components/StatusStrip.jsx'
import Overview from './screens/Overview.jsx'
import Workstation from './screens/Workstation.jsx'
import Memory from './screens/Memory.jsx'
import Playground from './screens/Playground.jsx'
import Analytics from './screens/Analytics.jsx'

const SCREENS = { overview: Overview, workstation: Workstation, memory: Memory, playground: Playground, analytics: Analytics }

export default function App() {
  const [view, setView] = useState('overview')
  const Screen = SCREENS[view]
  return (
    <div className="grid min-h-screen lg:grid-cols-[248px_1fr]">
      <Sidebar view={view} setView={setView} />
      <main className="flex min-w-0 flex-col gap-4 p-4 lg:p-6">
        <StatusStrip />
        <Screen setView={setView} />
      </main>
    </div>
  )
}

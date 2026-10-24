import React from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { RobotProvider } from './RobotContext.jsx'

createRoot(document.getElementById('root')).render(
  <RobotProvider>
    <App />
  </RobotProvider>,
)

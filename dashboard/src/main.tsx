import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@shared/styles/global.css'
import App from './App.tsx'

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

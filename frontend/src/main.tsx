import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MotionConfig } from 'motion/react'
import App from './App'
import './styles.css'
import './files.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* Hormati preferensi "kurangi gerakan" milik sistem */}
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </StrictMode>,
)

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// fontes da identidade servidas pelo proprio app (rede interna, sem Google Fonts)
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import '@fontsource/ibm-plex-mono/600.css'
import './index.css'
// depois de index.css de proposito: tokens.css e' o mundo visual e vence as
// regras soltas de la'.
import './tokens.css'
import App from './App.tsx'
import ErrorBoundary from './ErrorBoundary.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)

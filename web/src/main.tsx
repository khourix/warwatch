import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-sans-condensed/500.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/source-serif-4/400.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import './styles.css'
import App from './App'
import { PrefsProvider } from './settings'

// The data is rebuilt every 30 minutes; refetch on focus after 5 so a tab left open catches the next run.
const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 5 * 60_000, refetchOnWindowFocus: true, retry: 1 } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}><PrefsProvider><App /></PrefsProvider></QueryClientProvider>
  </StrictMode>,
)

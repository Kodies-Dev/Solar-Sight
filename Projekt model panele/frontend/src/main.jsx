import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { MantineProvider, createTheme } from '@mantine/core'
import '@mantine/core/styles.css'
import './index.css'

const theme = createTheme({
  fontFamily: 'Google Sans, sans-serif',
  headings: {
    fontFamily: 'Google Sans, sans-serif',
  },
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MantineProvider theme={theme}>
      <App />
    </MantineProvider>
  </StrictMode>,
)

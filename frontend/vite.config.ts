import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build outputs to dist/, which the nginx stage copies into the web root.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
})

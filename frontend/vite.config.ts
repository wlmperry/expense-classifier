import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // The default `forks` pool spawns a child process per worker, which is
    // slow to start on Windows and times out on some machines. `threads` is
    // faster to start and avoids that.
    pool: 'threads',
  },
})

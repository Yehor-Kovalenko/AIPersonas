import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import * as fs from "fs";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    https: {
      key: fs.readFileSync('../backend/env/key.pem'),
      cert: fs.readFileSync('../backend/env/cert.pem'),
    },
    host: '0.0.0.0'
  },
})

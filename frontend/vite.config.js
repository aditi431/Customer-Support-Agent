import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

const frontendDirectory = dirname(fileURLToPath(import.meta.url))
const projectDirectory = resolve(frontendDirectory, '..')

export default defineConfig(({ mode }) => {
  const serverEnv = loadEnv(mode, projectDirectory, '')
  const apiAccessToken = serverEnv.API_ACCESS_TOKEN
  const apiTarget = serverEnv.VITE_SUPPORT_API_PROXY || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          configure(proxy) {
            proxy.on('proxyReq', (proxyRequest) => {
              if (apiAccessToken) {
                proxyRequest.setHeader('X-API-Key', apiAccessToken)
              }
            })
          },
        },
      },
    },
  }
})

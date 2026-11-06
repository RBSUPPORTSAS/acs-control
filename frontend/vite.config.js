import { defineConfig } from 'vite'

// Solo para desarrollo y pruebas locales (npm run dev / npm run preview).
// En produccion Nginx sirve el build y reenvia /api al backend; este
// archivo no cambia el resultado de `npm run build`.
const api = process.env.ACS_API_URL || 'http://127.0.0.1:8000'

const proxy = {
    '/api': api,
    '/docs': api,
    '/openapi.json': api,
}

export default defineConfig({
    server: { host: '127.0.0.1', port: 5173, proxy },
    preview: { host: '127.0.0.1', port: 4173, proxy },
})

// Single configuration boundary for the backend API's base URL.
// Every request the app makes to the backend should go through this constant
// rather than reading import.meta.env directly elsewhere.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

// Shared bearer token sent with every API request; must match the backend's
// API_AUTH_TOKEN. This is baked into the built JS bundle at build time, same
// build-time-only limitation as API_BASE_URL -- it deters casual/bot abuse
// of the shared demo dataset, it is not a real secret once deployed.
export const API_AUTH_TOKEN = import.meta.env.VITE_API_AUTH_TOKEN ?? ''

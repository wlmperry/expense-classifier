// Single configuration boundary for the backend API's base URL.
// Every request the app makes to the backend should go through this constant
// rather than reading import.meta.env directly elsewhere.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

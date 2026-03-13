// Development environment - uses Vite proxy for same-origin requests
// The proxy in vite.config.ts redirects /api and /auth to http://localhost:8000
export const environment = {
  production: false,
  apiUrl: ''  // Empty to use relative URLs (proxied by Vite)
};


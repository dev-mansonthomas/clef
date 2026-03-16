# PWA Testing Guide

This guide explains how to test the Progressive Web App (PWA) features of the CLEF applications.

## Prerequisites

- Node.js installed
- Apps built in production mode
- Chrome/Edge browser (for best PWA support)

## Building the Apps

Build both apps in production mode to enable service workers:

```bash
cd frontend
npx ng build admin --configuration=production
npx ng build form --configuration=production
```

## Serving the PWA Builds

Use the provided server script to serve the production builds:

```bash
# Serve form app on http://localhost:8080
node serve-pwa.js form

# Serve admin app on http://localhost:8080
node serve-pwa.js admin
```

## Testing PWA Features

### 1. Service Worker Registration

1. Open the app in Chrome
2. Open DevTools (F12)
3. Go to Application tab → Service Workers
4. Verify that `ngsw-worker.js` is registered and activated

### 2. Offline Functionality

1. With the app open, go to DevTools → Network tab
2. Check "Offline" checkbox
3. Refresh the page
4. The app should still load from cache
5. Navigate to different routes - they should work offline

### 3. Install Prompt (Mobile)

On mobile devices:
1. Open the app in Chrome/Safari
2. Look for "Add to Home Screen" prompt
3. Install the app
4. Launch from home screen - should open in standalone mode

### 4. Lighthouse PWA Audit

Run Lighthouse to check PWA score:

```bash
# Make sure the app is running first
npx lighthouse http://localhost:8080 --view --only-categories=pwa
```

Target: PWA score > 90

### 5. Background Sync (Form App Only)

1. Open the form app
2. Fill out a form
3. Go offline (DevTools → Network → Offline)
4. Submit the form
5. Check browser console - should see "queued for sync"
6. Go back online
7. Form should auto-sync to server

## PWA Configuration Files

### Service Worker Config (`ngsw-config.json`)

- **app**: Prefetch critical app files
- **assets**: Lazy-load images and fonts
- **api-cache**: Cache API responses with freshness strategy
- **form-submissions**: Cache form data for offline support

### Manifest (`manifest.json`)

- App name and description
- Theme colors (Croix-Rouge red: #e30613)
- Icons (192x192 and 512x512)
- Display mode: standalone
- Start URL and scope

### Offline Page (`offline.html`)

Fallback page shown when offline and no cached content available.

## Troubleshooting

### Service Worker Not Updating

1. Go to DevTools → Application → Service Workers
2. Check "Update on reload"
3. Click "Unregister" to remove old service worker
4. Refresh the page

### Cache Issues

1. Go to DevTools → Application → Storage
2. Click "Clear site data"
3. Refresh the page

### Icons Not Showing

Current icons are SVG placeholders. For production:
1. Create proper PNG icons (192x192 and 512x512)
2. Use tools like:
   - https://realfavicongenerator.net/
   - https://www.pwabuilder.com/imageGenerator
3. Replace SVG files in `public/` directory
4. Update manifest.json to use `.png` instead of `.svg`

## Production Deployment

For production deployment:

1. Replace SVG icons with proper PNG icons
2. Ensure HTTPS is enabled (required for service workers)
3. Configure proper cache headers on server
4. Test on real mobile devices
5. Monitor service worker updates in production

## Resources

- [Angular Service Worker Guide](https://angular.dev/ecosystem/service-workers)
- [PWA Checklist](https://web.dev/pwa-checklist/)
- [Service Worker Lifecycle](https://web.dev/service-worker-lifecycle/)

